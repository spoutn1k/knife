import os
import psycopg2
from knife.helpers import complain
from knife.drivers import AbstractDriver
from knife.models import Datatypes

DRIVER_NAME = 'pgsql'
DBURL = complain('DATABASE_URL')


def model_definition(model):
    datatypes = {
        Datatypes.text: 'TEXT',
        Datatypes.required: 'NOT NULL',
        Datatypes.primary_key: ''
    }

    TEMPLATE = "CREATE TABLE %s (%%s)" % model.table_name
    columns = []
    pks = []

    for field in model.fields.fields:
        modifiers = [datatypes[dt] for dt in field.datatypes]
        columns.append("%s %s" % (str(field), " ".join(modifiers)))

    for field in model.fields.fields:
        if Datatypes.primary_key in field.datatypes:
            pks.append(str(field))

    columns.append("PRIMARY KEY (%s)" % ", ".join(pks))

    return TEMPLATE % (", ".join(columns))


def match_string(filters: list, exact: bool):
    parameters = {}

    if valid_filters := list(filter(lambda x: x, filters)):
        match_operator = '=' if exact else 'LIKE'
        template = ' WHERE '

        rules = []
        for index, f in enumerate(valid_filters):
            rule = []
            for column, value in f.items():
                if not exact:
                    value = "%%%s%%" % value
                parameters.update({"%s_%d" % (column, index): value})
                rule.append("%s %s %%(%s_%d)s" %
                            (column, match_operator, column, index))
            rules.append(" AND ".join(rule))

        template += " OR ".join(rules)

        return template, parameters
    return '', {}


def transaction(func):
    def wrapper(*args, **kwargs):
        driver, model = args[:2]

        if isinstance(model, tuple):
            table = (model[0].table_name, model[1].table_name, *model[2:])
        else:
            table = model.table_name

        args = (driver, table, *args[2:])

        driver.setup()
        template, parameters = func(*args, **kwargs)
        print(template, parameters)
        driver.cursor.execute(template, parameters)

        try:
            data = driver.cursor.fetchall()
        except psycopg2.ProgrammingError:
            data = []

        driver.close()

        if 'columns' in func.__code__.co_varnames:
            if (columns := kwargs.get('columns', ['*'])) == ['*']:
                columns = list(model.fields)
            data = [dict(zip(columns, record)) for record in data]

        return data

    wrapper.__name__ = func.__name__
    return wrapper


class PostGresDriver(AbstractDriver):
    def setup(self, params=None):
        self.connexion = psycopg2.connect(DBURL, sslmode='require')
        self.cursor = self.connexion.cursor()

    def close(self):
        self.connexion.commit()
        self.connexion.close()

    @transaction
    def read(self, table, filters=[], columns=['*'], exact=True):
        if isinstance(table, tuple) and len(table) == 4:
            table = "%s JOIN %s ON %s.%s = %s.%s" % (
                table[0], table[1], table[0], table[2], table[1], table[3])

        template = 'SELECT %s FROM %s' % (', '.join(columns), table)

        addendum, parameters = match_string(filters, exact)

        return template + addendum, parameters

    @transaction
    def write(self, table: str, record: dict, filters=[]) -> None:
        if filters:
            # if filters are there, we update values

            # Put a stamp in case a key is both a filter and a target
            values = ', '.join(
                ["%s = %%(record_%s)s" % (k, k) for k in record.keys()])
            stamped_record = dict([('record_' + k, v)
                                   for (k, v) in record.items()])

            template = 'UPDATE %s SET %s' % (table, values)

            addendum, parameters = match_string(filters, True)

            if not addendum:
                raise ValueError(filters)

            template += addendum
            parameters.update(stamped_record)

        else:
            # if not, a simple insert
            columns = ', '.join(record.keys())
            values = ', '.join(["%%(%s)s" % key for key in record.keys()])

            template = 'INSERT INTO %s (%s) VALUES (%s)' % (table, columns,
                                                            values)
            parameters = record

        return template, parameters

    @transaction
    def erase(self, table: str, filters=[]) -> None:
        template = 'DELETE FROM %s' % table

        addendum, parameters = match_string(filters, True)

        if not addendum:
            raise ValueError(filters)

        return template + addendum, parameters


DRIVER = PostGresDriver

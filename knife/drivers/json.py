from tinydb import (Query, TinyDB)
import logging
from knife.helpers import complain
from knife.drivers import AbstractDriver
from knife.models import Datatypes

DRIVER_NAME = 'json'


def build_query(filters, exact):
    query = None
    for rule in filter(None, filters):
        current = None
        for field, value in rule.items():
            if exact:
                fragment = getattr(Query(), field).matches(value)
            else:
                fragment = getattr(Query(), field).search(value)
            current = (current & fragment) if current else fragment
        query = (query | current) if query else current

    return query


def join(db, join_params, query):
    model1, model2, field1, field2 = join_params

    if query:
        lhs = db.table(model1.table_name, cache_size=0).search(query)
    else:
        lhs = db.table(model1.table_name, cache_size=0).all()

    for document in lhs:
        assert len(document.keys()) == len(model1.fields.fields)
        query = getattr(Query(), field2).matches(document[field1])
        rhs = db.table(model2.table_name, cache_size=0).search(query)

        for other in rhs:
            yield document | other


def select(mapping: dict, fields: list[str]):
    if fields == ['*']:
        return mapping

    keys = list(mapping.keys())
    for field in keys:
        if field not in fields:
            del mapping[field]

    return mapping


class JSONDriver(AbstractDriver):

    def __init__(self, database_location):
        self.db = TinyDB(database_location)

    def read(self,
             model: object,
             filters=[],
             columns=['*'],
             exact=True) -> dict:
        matches = []

        if isinstance(model, tuple):
            # We need to join tables manually
            query = build_query(filters, exact)

            matches = list(join(self.db, model, query))
        else:
            table = self.db.table(model.table_name, cache_size=0)

            if query := build_query(filters, exact):
                matches = table.search(build_query(filters, exact))
            else:
                matches = table.all()

        return list(map(lambda x: select(x, columns), matches))

    def write(self, model: object, record: dict, filters=[]) -> None:
        table = self.db.table(model.table_name, cache_size=0)

        if filters:
            query = build_query(filters, True)
            table.update(record, query)

        else:
            table.insert(record)

    def erase(self, model: object, filters=[]) -> None:
        table = self.db.table(model.table_name, cache_size=0)

        if query := build_query(filters, True):
            table.remove(query)
        else:
            raise ValueError(filters)


DRIVER = JSONDriver

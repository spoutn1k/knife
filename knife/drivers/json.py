from tinydb import (Query, TinyDB)
from typing import Any
from knife.drivers import AbstractDriver
from knife.models.knife_model import Field, KnifeModel

DRIVER_NAME = 'json'


def build_query(filters, exact):
    query = None
    for rule in filter(None, filters):
        current = None
        for field, value in rule.items():
            if exact:
                fragment = getattr(Query(), field.name) == value
            else:
                fragment = getattr(Query(), field.name).search(value)
            current = (current & fragment) if current else fragment
        query = (query | current) if query else current

    return query


def join(db, join_params, query):
    """Mimic SQL join by querying twice and merging the records"""
    model1, model2, field1, field2 = join_params

    if query:
        lhs = db.table(model1.table_name, cache_size=0).search(query)
    else:
        lhs = db.table(model1.table_name, cache_size=0).all()

    for document in lhs:
        assert len(document.keys()) == len(model1.fields.fields)
        query = getattr(Query(), field2.name).matches(document[field1.name])
        rhs = db.table(model2.table_name, cache_size=0).search(query)

        for other in rhs:
            yield document | other


def select(mapping: dict, fields: list[Field], model: KnifeModel):
    """Filter a mapping and return only the fields present in fields"""
    if fields == ['*']:
        if isinstance(model, tuple):
            fields = set(model[0].fields.fields) | set(model[1].fields.fields)
        else:
            fields = model.fields.fields

    def cast_fields(
        mapping: dict[str, Any],
        fields: set[Field],
    ) -> dict[Field, Any]:
        """Transform mapping keys in model fields"""
        target_field_names = dict(map(lambda x: (x.name, x), fields))
        for field_name, value in mapping.items():
            if field_name in target_field_names:
                yield (target_field_names[field_name], value)

    return dict(cast_fields(mapping, fields))


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
                matches = table.search(query)
            else:
                matches = table.all()

        return list(map(lambda x: select(x, columns, model), matches))

    def write(self, model: object, record: dict, filters=[]) -> None:
        table = self.db.table(model.table_name, cache_size=0)

        cast_record = dict(
            map(
                lambda k_v: (k_v[0].name, k_v[1]),
                record.items(),
            ))

        if filters:
            query = build_query(filters, True)
            table.update(cast_record, query)

        else:
            table.insert(cast_record)

    def erase(self, model: object, filters=[]) -> None:
        table = self.db.table(model.table_name, cache_size=0)

        if query := build_query(filters, True):
            table.remove(query)
        else:
            raise ValueError(filters)


DRIVER = JSONDriver

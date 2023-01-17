from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Ingredient(KnifeModel):
    table_name = 'ingredients'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='name', datatype=[Datatypes.TEXT]),
        Field(name='simple_name', datatype=[Datatypes.TEXT]),
        Field(name='dairy', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='gluten', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='meat', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='animal_product',
              datatype=[Datatypes.BOOLEAN],
              default=False),
    )

    def serializable(self, **kwargs):
        return kwargs | {
            self.fields.id.name: self.id,
            self.fields.name.name: self.name,
            self.fields.simple_name.name: self.simple_name,
            'classifications': {
                self.fields.gluten.name: self.gluten,
                self.fields.animal_product.name: self.animal_product,
                self.fields.dairy.name: self.dairy,
                self.fields.meat.name: self.meat,
            }
        }

class KnifeError(Exception):
    def __init__(self):
        super().__init__()
        self.data = None
        self.status = 500


class InvalidQuery(KnifeError):
    def __init__(self, param):
        super().__init__()
        self.param = param
        self.status = 400

    def __str__(self):
        return "Invalid parameter: %s" % str(self.param)


class EmptyQuery(KnifeError):
    def __init__(self):
        super().__init__()
        self.status = 400

    def __str__(self):
        return "Expected parameters"


class InvalidValue(KnifeError):
    def __init__(self, field, value):
        super().__init__()
        self.field = field
        self.value = value

    def __str__(self):
        return "Invalid field %s (%s)" % (self.field, self.value)


class IngredientNotFound(KnifeError):
    def __init__(self, ingredient_id):
        super().__init__()
        self.ingredient_id = ingredient_id
        self.status = 404

    def __str__(self):
        return "Ingredient not found: %s" % self.ingredient_id


class IngredientAlreadyExists(KnifeError):
    def __init__(self, ingredient_data):
        super().__init__()
        self.data = ingredient_data
        self.status = 409

    def __str__(self):
        return "Ingredient already exists"


class IngredientInUse(KnifeError):
    def __init__(self, use_count):
        super().__init__()
        self.use_count = use_count
        self.status = 409

    def __str__(self):
        return "Ingredient in use"


class RecipeNotFound(KnifeError):
    def __init__(self, recipe_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.status = 404

    def __str__(self):
        return "Recipe not found: %s" % self.recipe_id


class RecipeAlreadyExists(KnifeError):
    def __init__(self, recipe_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.status = 409

    def __str__(self):
        return "Recipe already exists"


class RequirementNotFound(KnifeError):
    def __init__(self, recipe_id, ingredient_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.ingredient_id = ingredient_id
        self.status = 404

    def __str__(self):
        return "Requirement not found"


class RequirementAlreadyExists(KnifeError):
    def __init__(self, recipe_id, ingredient_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.ingredient_id = ingredient_id
        self.status = 409

    def __str__(self):
        return "Requirement already exists"


class LabelInvalid(KnifeError):
    def __init__(self, label_name):
        super().__init__()
        self.label_name = label_name
        self.status = 400

    def __str__(self):
        return "Invalid label name: {}".format(self.label_name)


class LabelAlreadyExists(KnifeError):
    def __init__(self, label_data):
        super().__init__()
        self.data = label_data
        self.status = 409

    def __str__(self):
        return "Label already exists"


class LabelNotFound(KnifeError):
    def __init__(self, label_id):
        super().__init__()
        self.label_id = label_id
        self.status = 404

    def __str__(self):
        return "Label not found"


class TagAlreadyExists(KnifeError):
    def __init__(self, recipe_id, label_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.label_id = label_id
        self.status = 409

    def __str__(self):
        return "Tag already exists"


class TagNotFound(KnifeError):
    def __init__(self, recipe_id, label_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.label_id = label_id
        self.status = 404

    def __str__(self):
        return "Tag not found"


class DepencyAlreadyExists(KnifeError):
    def __init__(self):
        super().__init__()
        self.status = 409

    def __str__(self):
        return "Dependency already exists"


class DependencyNotFound(KnifeError):
    def __init__(self, recipe_id, required_id):
        super().__init__()
        self.recipe_id = recipe_id
        self.required = required_id
        self.status = 404

    def __str__(self):
        return "Dependency not found"

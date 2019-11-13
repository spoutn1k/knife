class KnifeError(Exception):
    pass

class InvalidQuery(KnifeError):
    def __init__(self, param):
        self.param = param
    def __str__(self):
        return "Invalid parameter: {}".format(self.param)

class IngredientNotFound(KnifeError):
    def __init__(self, ingredient_id):
        self.ingredient_id = ingredient_id
    def __str__(self):
        return "Ingredient not found"

class IngredientAlreadyExists(KnifeError):
    def __init__(self, ingredient_id):
        self.ingredient_id = ingredient_id
    def __str__(self):
        return "Ingredient already exists"

class IngredientInUse(KnifeError):
    def __init__(self, use_count):
        self.use_count = use_count
    def __str__(self):
        return "Ingredient in use"

class DishNotFound(KnifeError):
    def __init__(self, dish_id):
        self.dish_id = dish_id
    def __str__(self):
        return "Dish not found"

class DishAlreadyExists(KnifeError):
    def __init__(self, dish_id):
        self.dish_id = dish_id
    def __str__(self):
        return "Dish already exists"

class RequirementNotFound(KnifeError):
    def __init__(self, dish_id, ingredient_id):
        self.dish_id = dish_id
        self.ingredient_id = ingredient_id
    def __str__(self):
        return "Requirement not found"

class RequirementAlreadyExists(KnifeError):
    def __init__(self, dish_id, ingredient_id):
        self.dish_id = dish_id
        self.ingredient_id = ingredient_id
    def __str__(self):
        return "Requirement already exists"

class LabelInvalid(KnifeError):
    def __init__(self, label_name):
        self.label_name = label_name
    def __str__(self):
        return "Invalid label name: {}".format(self.label_name)

class LabelAlreadyExists(KnifeError):
    def __init__(self, labelname):
        self.labelname = labelname
    def __str__(self):
        return "Label already exists"

class LabelNotFound(KnifeError):
    def __init__(self, label_id):
        self.label_id = label_id
    def __str__(self):
        return "Label not found"

class TagAlreadyExists(KnifeError):
    def __init__(self, dish_id, label_id):
        self.dish_id = dish_id
        self.label_id = label_id
    def __str__(self):
        return "Tag already exists"

class TagNotFound(KnifeError):
    def __init__(self, dish_id, label_id):
        self.dish_id = dish_id
        self.label_id = label_id
    def __str__(self):
        return "Tag not found"

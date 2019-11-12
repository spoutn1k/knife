# Knife

## List of supported actions
|Method|URL|Action|
|-|-|-|
|`GET`|`/ingredients`|Returns a list of ingredients, with search on GET arguments|
|`POST`|`/ingredients/new`|Creates a new ingredient, with data passed in the json field of the request|
|`DELETE`|`/ingredients/<ingredientid>`|Method on ingredient objects|
|-|-|-|
|`GET`|`/dishes`|List recorded dishes, search available with GET arguments|
|`POST`|`/dishes/new`|Create a new dish|
|`GET,DELETE`|`/dishes/<dishid>`|Methods on dish objects|
|-|-|-|
|`GET`|`/dishes/<dishid>/ingredients`|Get a dish's requirements|
|`POST`|`/dishes/<dishid>/ingredients/add`|Add a requirement to a recipe|
|`PUT,DELETE`|`/dishes/<dishid>/ingredients/<ingredientid>`|Modify or delete a requirement|
|-|-|-|
|`GET`|`/dishes/<dishid>/tags`|List a dish's labels|
|`POST`|`/dishes/<dishid>/tags/add`|Tag a dish with a label|
|`DELETE`|`/dishes/<dishid>/tags/<labelname>`|Delete a tag from a dish|
|-|-|-|
|`GET`|`/labels`|List available labels|
|`GET`|`/labels/<labelid>`|List the dishes associated with a specific label|
|`DELETE`|`/labels/<labelid>`|Delete a specific label|

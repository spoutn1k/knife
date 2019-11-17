# Knife

## List of supported actions
|Method|URL|Action|
|-|-|-|
|`GET`|`/ingredients`|Returns a list of ingredients, with search on GET arguments|
|`POST`|`/ingredients/new`|Creates a new ingredient|
|`PUT`|`/ingredients/<ingredientid>`|Modifies an ingredient object|
|`DELETE`|`/ingredients/<ingredientid>`|Deletes an ingredient object|
|`PUT`|`/ingredients/<ingredientid>/merge`|Merges two ingredient by associating every requirement to `ingredientid`|
|-|-|-|
|`GET`|`/dishes`|Lists recorded dishes, search available with GET arguments|
|`POST`|`/dishes/new`|Creates a new dish|
|`GET,PUT,DELETE`|`/dishes/<dishid>`|Methods on dish objects|
|-|-|-|
|`GET`|`/dishes/<dishid>/requirements`|Get a dish's requirements|
|`POST`|`/dishes/<dishid>/requirements/add`|Adds a requirement to a recipe|
|`PUT`|`/dishes/<dishid>/requirements/<ingredientid>`|Modifies a requirements quantity|
|`DELETE`|`/dishes/<dishid>/requirements/<ingredientid>`|Deletes a requirement|
|-|-|-|
|`GET`|`/dishes/<dishid>/dependencies`|Lists a dish's dependencies|
|`POST`|`/dishes/<dishid>/dependencies/add`|Adds a pre-requisite recipe to the dish|
|`DELETE`|`/dishes/<dishid>/dependencies/<requiredid>`|Deletes a dependency from a recipe|
|-|-|-|
|`GET`|`/dishes/<dishid>/tags`|Lists a dish's labels|
|`POST`|`/dishes/<dishid>/tags/add`|Tags a dish with a label|
|`DELETE`|`/dishes/<dishid>/tags/<labelname>`|Deletes a tag from a dish|
|-|-|-|
|`GET`|`/labels`|Lists available labels|
|`GET`|`/labels/<labelid>`|Lists the dishes associated with a specific label|
|`PUT`|`/labels/<labelid>`|Modifies a label name|
|`DELETE`|`/labels/<labelid>`|Deletes a label and associated tags|

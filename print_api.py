import os

os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['DATABASE_URL'] = 'no'

from knife import routes
from knife.models import (Ingredient, Recipe, Requirement, Tag, Dependency,
                          Label)

import re
import ast
import inspect
from pprint import pprint
from dataclasses import dataclass
from textwrap import indent


def load_symbol(node: ast.Attribute | ast.Name) -> str:
    if isinstance(node, ast.Attribute):
        return f"{load_symbol(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id


@dataclass(frozen=True)
class Parameter:
    name: str
    location: str
    required: bool = False

    def yaml(self):
        return f"""- in: {self.location}
  name: {self.name}
  required: {str(self.required).lower()}
  schema:
    type: string"""


def pattern_from_path(path: str) -> (str, list[Parameter]):
    found = set()
    path_params = re.findall(r'<\w+>', path)
    for param in path_params:
        name = param.strip('<>')
        found.add(Parameter(
            name=name,
            location='path',
            required=True,
        ))
    path = path.replace('<', '{').replace('>', '}')

    return path, found


class ValidatorGatherer(ast.NodeVisitor):

    def __init__(self):
        super().__init__()
        self.consts = []

    def generic_visit(self, node):
        if isinstance(node, ast.Call):
            if isinstance(node.func,
                          ast.Name) and node.func.id == 'validate_query':
                self.consts = list(
                    map(eval, map(load_symbol, node.args[1].elts)))
        ast.NodeVisitor.generic_visit(self, node)


def transform_routes(routes: list) -> dict[str, set[tuple[str, any]]]:
    defined = {}
    for methods, endpoint, path in routes:
        defined[path] = {(methods[0], endpoint)} | defined.get(path, set())
    return defined


defined = transform_routes(routes.ROUTES)
for path in defined:
    escaped_path, params = pattern_from_path(path)
    print(f"""  "{escaped_path}":""")

    for method, endpoint in defined.get(path):
        endpoint = endpoint.__closure__[0].cell_contents.__func__
        nv = ValidatorGatherer()
        source = "\n".join(
            list(
                filter(
                    None,
                    map(lambda x: x[4:],
                        inspect.getsource(endpoint).split('\n')))))
        nv.visit(ast.parse(source))
        local = {Parameter(name, 'header') for name in nv.consts}

        parameters = "\n".join(map(lambda x: x.yaml(), local | params))
        parameters = indent(parameters, ' ' * 6)

        print(f"""    {method.lower()}:
      parameters:
{parameters}
      responses:
""",
              end="")

"""Static input layouts for public typed functions; no runtime data enters compilation."""
from frontend.language_surface.nodes import (
    ArrayTypeNode, NamedTypeNode, OptionalTypeNode, PrimitiveTypeNode,
    StructDeclarationNode, FunctionDeclarationNode, TupleTypeNode, Visibility,
)

VERSION = 'reasonscript-input/1.0'

def input_contract(program):
    from frontend.foundation.integration import COMPLEX_TYPES
    definitions = {}
    modules = {}
    for module in program.modules:
        namespace = f'{program.package.name}.{module.name}' if program.package else module.name
        modules[module.name] = namespace
        for node in module.body:
            if isinstance(node, StructDeclarationNode):
                definitions[f'{namespace}.{node.name}'] = (namespace, node)

    def layout(t, namespace):
        if isinstance(t, PrimitiveTypeNode):
            return t.kind.value
        if isinstance(t, ArrayTypeNode):
            return {'array': layout(t.element_type, namespace)}
        if isinstance(t, OptionalTypeNode):
            return {'optional': layout(t.inner_type, namespace)}
        if isinstance(t, TupleTypeNode):
            return {'tuple': [layout(x, namespace) for x in t.element_types]}
        if isinstance(t, NamedTypeNode):
            if t.name in COMPLEX_TYPES:
                return {"struct": f"complex.{t.name}"}
            name = t.name.replace('::', '.')
            candidates = [n for n in definitions if n == name or n == f'{namespace}.{name}']
            if not candidates:
                candidates = [n for n in definitions if n.rsplit('.', 1)[-1] == name]
            if len(candidates) == 1:
                return {'struct': candidates[0]}
        return {'unsupported': str(t)}

    structs = {name: {'type_name': node.name, 'fields': {f.name: layout(f.field_type, namespace) for f in node.fields}}
               for name, (namespace, node) in definitions.items()}
    structs.update({f"complex.{name}": {"type_name": name, "fields": {k: layout(t, "complex") for k,t in fields.items()}} for name, fields in COMPLEX_TYPES.items()})
    entries = {}
    for module in program.modules:
        namespace = modules[module.name]
        for node in module.body:
            if isinstance(node, FunctionDeclarationNode) and node.visibility != Visibility.PRIVATE:
                entries[f'fn.{namespace}::{node.name}'] = {'parameters': {
                    p['name']: layout(p['type'], namespace) for p in node.parameters
                }}
    return {'version': VERSION, 'entries': entries, 'structs': structs}

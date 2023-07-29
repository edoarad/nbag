from inspect import Signature, Parameter
import inspect
import sys
import inspect
from functools import reduce
from dataclasses import dataclass
from typing import Callable


def should_wrap(signature: Signature):
    params = signature.parameters
    if not params: return False
    p0 = next(iter(signature.parameters.values()))
    if p0.name != "name": return False
    return ((p0.annotation is p0.empty)
            or (p0.annotation is str))

@dataclass
class ArgsGenerator:
    parameters: list[Parameter]

    def declared_args(self, after_pok=[]):
        po_args = []
        pok_args = []
        kwo_args = []
        any_star = False
        any_kw_only = False
        for p in self.parameters:
            s = ""
            if p.kind == p.POSITIONAL_ONLY:
                args = po_args
            elif p.kind == p.POSITIONAL_OR_KEYWORD:
                args = pok_args
            elif p.kind == p.VAR_POSITIONAL:
                args = po_args
                s += '*'
                any_star = True
            elif p.kind == p.KEYWORD_ONLY:
                args = kwo_args
                any_kw_only = True
            elif p.kind == p.VAR_KEYWORD:
                s += '**'
                args = kwo_args
            else:
                assert False, "unexpected parameter kind: "+repr(p)

            s += p.name
            if p.annotation is not inspect._empty:
                s += ':' + str(s.annotation)
            if p.default is not inspect._empty:
                s += '=' + repr(p.default)
            args.append(s) 

        slashes = ["/"] if po_args else []
        stars = ["*"] if (any_kw_only and not any_star) else []
        return ', '.join(po_args + slashes + pok_args + after_pok + stars + kwo_args)

    def pass_positionals(self):
        positional = []
        for p in self.parameters:
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                positional.append(p.name)
                continue
            if p.kind==p.VAR_POSITIONAL:
                if not positional: return p.name
                positional.append(f"*{p.name}")
                break
            assert p.kind in (p.VAR_KEYWORD, p.KEYWORD_ONLY)
            break
        return positional
        
    def pass_kw(self):
        bindings = []
        for p in self.parameters:
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL):
                continue
            if p.kind == p.KEYWORD_ONLY:
                bindings.append(f"{repr(p.name)}: {p.name}")
                continue
            if p.kind == p.VAR_KEYWORD:
                bindings.append(f"**{p.name}")
                continue
            assert False
        return bindings 

   
@dataclass
class WrapperCode:
    name: str
    imports: list[str]
    definition: str

def wrap_function(f: Callable, module_path: str):
    s = inspect.signature(f)
    if not should_wrap(s): return None
    qualified_f_name = module_path + "." + f.__name__
    params = list(s.parameters.values())[1:] # skip the first parameter which is assumed to be "name"
    args = ArgsGenerator(params)
    imports = [module_path]
    wrapper_formal_args = args.declared_args(["name=None"])
    construct_args = ', '.join([qualified_f_name, "name"] + args.pass_positionals() + args.pass_kw())
    definition = (
            f"def {f.__name__}({wrapper_formal_args}):\n"
            +f"    return construct({construct_args})\n"
            )
    return WrapperCode(f.__name__, imports, definition)

def wrap_module(module_path, dest, names=None):
    from importlib import import_module
    module = import_module(module_path)
    if names is None:
        names = [name for name in dir(module) if not name.startswith('_')]

    objects = {name: getattr(module, name) for name in names}
    functions = {name:v for (name,v) in objects.items() if callable(v)}
    wrappers = [wrap_function(v, module_path) for v in functions.values()]
    wrappers = [w for w in wrappers if w]

    imports = sorted(reduce(frozenset.union, [w.imports for w in wrappers], frozenset()))
    with open(dest, 'w') as out:
        print("from named_by_assignment import construct", file=out)
        for module in imports:
            print("import "+module, file=out)
        print("\n", file=out)
        for w in wrappers:
            print(w.definition, file=out)


def ensure_module(p: str):
    import os, os.path
    if not os.path.exists(p):
        os.mkdir(p)
    init = os.path.join(p, "__init__.py")
    if not os.path.exists(init):
        with open(init,'w'):
            pass


def wrap_sympy_stats():
    import sympy.stats
    ensure_module("generated")
    ensure_module("generated/sympy")
    wrap_module('sympy.stats', "generated/sympy/stats.py")
    

if __name__ == '__main__':
    wrap_sympy_stats()

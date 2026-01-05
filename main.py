
import sys
import random
from dataclasses import dataclass
from math import ceil






def lex(src):
    def kind(char):
        match char:
            case '\0': return 'terminator'
            case ' ': return 'space'
            case x if x.isalpha(): return 'iden'
            case '_': return 'iden'
            case x if x.isdigit(): return 'iden'
            case '"': return 'quote'
            case '\n': return 'eos'
            case '(': return 'open'
            case ')': return 'close'
            case _: return 'sym'

    state = kind(src[0])
    ts = []
    buffer = ''

    comment = False
    string = False
    line_index = 0
    for char in src + '\0':
        this = kind(char)

        if buffer == '--': 
            #remove line indentation
            while ts[-1].strip(' ') == '':
                ts.pop(-1)
                line_index -= 1

            if line_index > 0 and ts[-1] != '\n':
                ts.append('\n')

            buffer = ''
            comment = True


        if buffer in ('Output', 'Console'):
            break

        if this != state and not comment and not string:
            #truncate eos
            if state == 'eos': buffer = '\n'

            if state != 'space' or line_index == 0:
                if not (buffer == '\n' and ts[-1] == '\n'):
                    ts.append(buffer)
            line_index += 1
            buffer = ''

        if char == '"':
            string = not string
        if state == 'eos': 
            comment = False
            line_index = 0

        if not comment:
            buffer += char
        state = this

    class streamer:
        def __init__(self, ts):
            self.ts = ts

        def push(self, x):
            self.ts.insert(0, x)

        def has(self):
            return len(self.ts) > 0

        def peek(self):
            return self.ts[0]

        def pop(self):
            return self.ts.pop(0)

        def expect(self, should):
            be = self.pop()
            if should != be:
                print(f"Lex error: Expected '{should}', but got '{be}'.")
                sys.exit(1)

    return streamer(ts)



builtin = {
    'number_nodec': 'number_nodec',
    'number_fixed': 'number_fixed',
    'string': 'string',
    'bool': 'bool',
    'list': 'list',
    'random': 'random',
    'true': True,
    'false': False,
    'input': None,
    'input_string': None,
    'input_number': None,
    'input_number_nodec': None,
    'input_math': None,
}

@dataclass
class leaf:
    name : ""
    method : "str | None"
    args : "list[a]"
    kind : str

    @classmethod
    def parse(cls, s):
        if s.peek() == '{':
            s.expect('{')
            elem = []
            while s.peek() != '}':
                if s.peek() == ',': s.pop()
                elif s.peek() == '\n': s.pop()
                elif s.peek().strip() == '': s.pop()
                else: elem.append(leaf.parse(s))
            s.expect('}')
            return cls(elem, None, None, 'list')

        if s.peek() == 'log':
            s.expect('log')
            s.expect('.')
            s.expect('userinput')
            s.expect('.')
            s.expect('(')
            text = s.pop()
            s.expect(',')
            kind = s.pop()
            s.expect(')')
            return cls(None, None, (text, kind), 'input')
            

        name = s.pop()
        method = None
        args = []
        kind = 'normal'

        if s.peek() == '.':
            kind = 'method'
            s.expect('.')
            method = s.pop()

            match method:
                case 'length' | 'upper' | 'lower' | 'randomize': pass
                case 'find': args.append(s.pop().strip('"'))

        elif s.peek() == '(':
            kind = 'call'
            s.push(name)
            method = ast_call.parse(s)

        return cls(name, method, args, kind)

    def run(self, env, fixed=False):
        if self.kind == 'method':
            val = env[self.name]["value"]
            match self.method:
                case 'length': return len(val)
                case 'upper':  return val.upper()
                case 'lower':  return val.lower()
                case 'find':   return self.args[0] if self.args[0] in val else 'null'
                case 'randomize': return random.randint(*val)

        if self.kind == 'input':
            answer = input(self.args[0].strip('"'))
            return eval(answer) if self.args[1] == 'input_mathN' else answer


        if self.kind == 'call':
            return self.method.run(env)

        if self.kind == 'list':
            return [x.run(env) for x in self.name]

        if self.name.isdigit(): return int(self.name)
        if self.name[0] == '"': return self.name.strip('"')
        if self.name in builtin: return builtin[self.name]
        
        if "value" in env[self.name]:
            return env[self.name]["value"]

        return env[self.name]




@dataclass
class expr:
    left  : "expr | leaf"
    right : "expr | leaf"
    op : str

    def run(self, env, fixed=False):
        l = self.left.run(env)
        r = self.right.run(env)

        return {
            '+':    lambda l,r: l + r,
            '-':    lambda l,r: l - r,
            '*':    lambda l,r: l * r,
            '/':    lambda l,r: 'infinity' if r == 0 and fixed else l / r,
            '>=':   lambda l,r: l >= r,
            '<=':   lambda l,r: l <= r,
            '==':   lambda l,r: l == r,
            '!=':   lambda l,r: l != r,
            'and':  lambda l,r: l and r,
            'or':   lambda l,r: l or r,
            '..':   lambda l,r: str(l) + str(r),
            ',':    lambda l,r: ((l, r)),
        }[self.op](l,r)


    @classmethod
    def parse(cls, s):
        left = leaf.parse(s)

        if s.peek() not in ('+', '-', '*', '/', '>=', '<=', '==', '!=', 'and', 'or', '..', ','):
            return left

        op = s.pop()
        right = expr.parse(s)
        return cls(left, right, op)




@dataclass
class ast_var_new:
    name : str

    @classmethod
    def parse(cls, s):
        return cls(s.pop())

    def run(self, env):
        env[self.name] = {"value" : 0}

@dataclass
class ast_var_set:
    name : str
    field : str
    value : expr
    inc : bool

    def run(self, env):
        if self.name not in env:
            print(f"Error: Variable {self.name} not defined")
            sys.exit(1)

        fixed = "type" in env[self.name] and env[self.name]["type"] == 'number_fixed'
        val = self.value.run(env, fixed)

        if self.inc:
            env[self.name][self.field] += val
        else:
            env[self.name][self.field] = val



    @classmethod
    def parse(cls, s):
        name = s.pop()
        s.expect('.')
        field = s.pop()
        inc = s.peek() == '+='
        s.expect('+=' if inc else "=")
        value = expr.parse(s)
        return cls(name, field, value, inc)


@dataclass
class ast_if:
    cond : expr
    then :      "prog"
    otherwise : "prog | None" #fuck you python

    def run(self, env):
        choice = self.cond.run(env)
        if choice:
            return self.then.run(env)
        elif self.otherwise is not None:
            return self.otherwise.run(env)

    @classmethod
    def parse(cls, s, scope):
        cond = expr.parse(s)
        s.expect(':')
        s.expect('\n')
        then = ast_prog.parse(s, scope)

        if s.peek() == 'else':
            s.expect('else')
            s.expect(':')
            s.expect('\n')
            otherwise = ast_prog.parse(s, scope)
        else:
            otherwise = None

        return cls(cond, then, otherwise)


@dataclass
class ast_log:
    val : expr

    def run(self, env):
        out = self.val.run(env)
        if type(out) is dict:
            for k, v in out.items():
                print(f"{k}: {v['value']}")
        else:
            print(out)

    @classmethod
    def parse(cls, s):
        s.expect('.')
        s.expect('print')
        s.expect('.')
        s.expect('(')
        val = expr.parse(s)
        s.expect(')')

        return cls(val)

@dataclass
class ast_try:
    body : "ast_prog"
    target : str
    catch : "ast_prog"

    def run(self, env):
        try:
            self.body.run(env)
        except Exception as E:
            env[self.target] = {}
            env[self.target]["value"] = str(E)
            self.catch.run(env)

    @classmethod
    def parse(cls, s, scope):
        s.expect(':')
        s.expect('\n')
        body = ast_prog.parse(s, scope)

        s.expect('catch')
        target = s.pop()
        s.expect(':')
        s.expect('\n')
        catch = ast_prog.parse(s, scope)

        return cls(body, target, catch)


@dataclass
class ast_class:
    name : str

    def run(self, env):
        env[self.name] = {}

    @classmethod
    def parse(cls, s):
        return cls(s.pop())

@dataclass
class ast_func:
    name : str
    params : "list[]"
    body : "prog"

    def run(self, env):
        env["_fn"][self.name] = self

    def call(self, env, args, constructer=None):
        for name, value in zip(self.params, args):
            env[name] = {"value": value}

        env["_con"] = constructer
        return self.body.run(env)

    @classmethod
    def parse(cls, s, scope):
        name = s.pop()
        params = []
        s.expect('(')
        while s.peek() != ')':
            params.append(s.pop())
            if s.peek() == ',': s.pop()
        s.expect(')')
        s.expect(':')
        s.expect('\n')
        body = ast_prog.parse(s, scope)
        return cls(name, params, body)

@dataclass
class ast_self:
    fields : list[str]

    def run(self, env):
        for name in self.fields:
            env[env["_con"]][name] = env[name]

    @classmethod
    def parse(cls, s):
        fields = []
        while s.peek() != '\n':
            fields.append(s.pop())
            if s.peek() == ',': s.pop()
        return cls(fields)

@dataclass
class ast_call:
    fn_name : str
    constructer : "str | None"
    params : list[expr]

    def run(self, env):
        param_vals = [x.run(env) for x in self.params]
        return env["_fn"][self.fn_name].call(env, param_vals, self.constructer)

    @classmethod
    def parse(cls, s, constructer=None):
        fn_name = s.pop()
        params = []
        s.expect('(')
        while s.peek() != ')':
            params.append(leaf.parse(s))
            if s.peek() == ',': s.pop()
        s.expect(')')
        return cls(fn_name, constructer, params)


@dataclass
class ast_return:
    res : expr

    def run(self, env):
        return self.res.run(env)

    @classmethod
    def parse(cls, s):
        return cls(expr.parse(s))

@dataclass
class ast_break:
    def run(self, _): pass
    @classmethod
    def parse(cls, _): return cls()

@dataclass
class ast_continue:
    def run(self, _): pass
    @classmethod
    def parse(cls, _): return cls()

@dataclass
class ast_repeat:
    n : expr
    body : ""

    def run(self, env):
        for _ in range(self.n.run(env)):
            status = self.body.run(env)
            if status is ast_continue: continue
            if status is ast_break: break

    @classmethod
    def parse(cls, s, scope):
        n = expr.parse(s)
        s.expect(':')
        s.expect('\n')
        body = ast_prog.parse(s, scope)
        return cls(n, body)


@dataclass
class ast_method:
    target : str
    method : str
    args : 'list'

    def run(self, env):
        match self.method:
            case 'new':
                l = env[self.target]["value"]
                index = self.args[1].run(env) - 1
                while len(l) <= index:
                    l.append(None)
                l[index] = self.args[0].run(env)
            case 'remove':
                index = self.args[0].run(env) - 1
                l = env[self.target]["value"]
                l.pop(index)



    @classmethod
    def parse(cls, s):
        target = s.pop()
        s.expect('.')
        method = s.pop()
        args = []
        if method == 'new':
            args.append(leaf.parse(s))
            s.expect(',')
            s.expect('index')
            s.expect('=')
            args.append(expr.parse(s))
        elif method == 'remove':
            s.expect('index')
            s.expect('=')
            args.append(expr.parse(s))

        return cls(target, method, args)



@dataclass
class ast_for:
    iter : str
    cont : expr
    body : ""

    def run(self, env):
        for elem in self.cont.run(env):
            env[self.iter] = elem
            self.body.run(env)

    @classmethod
    def parse(cls, s, scope):
        iter = s.pop()
        s.expect('in')
        cont = expr.parse(s)
        s.expect(':')
        s.expect('\n')
        body = ast_prog.parse(s, scope)
        return cls(iter, cont, body)



@dataclass
class ast_prog:
    prog : "list[ass]"

    def run(self, env):
        for stat in self.prog:
            if type(stat) is ast_return:
                return stat.run(env)

            if type(stat) is ast_continue: return ast_continue
            if type(stat) is ast_break:    return ast_break

            status = stat.run(env)
            if status is not None:
                if status in (ast_continue, ast_break):
                    return status



    @classmethod 
    def parse(cls, stream, scope=0):
        stats = [] 
        while stream.has():
            #check scope
            indent = 0
            indented = False
            if all(x == ' ' for x in stream.peek()):
                indented = True
                indent = ceil(len(stream.peek()) / 4)

            if indent != scope:
                break

            if indented:
                stream.pop()

            stat = None
            match stream.pop():
                case 'var':
                    if stream.peek() == '.':
                        stream.expect('.')
                        stream.expect('new')
                        stat = ast_var_new.parse(stream)
                    else:
                        stat = ast_var_set.parse(stream)
                case 'importpkg':
                    stream.expect('mkjExecutable')
                case 'mkjExecutable':
                    stream.expect(':')
                    stream.expect('activate')
                    stream.expect('(')
                    stream.expect('"main.mkj"')
                    stream.expect(')')
                case 'if':
                    stat = ast_if.parse(stream, scope+1)
                case 'log':
                    stat = ast_log.parse(stream)
                case 'attempt':
                    stat = ast_try.parse(stream, scope+1)
                case 'class':
                    stream.expect('.')
                    stream.expect('new')
                    stat = ast_class.parse(stream)
                case 'function':
                    stat = ast_func.parse(stream, scope+1)
                case 'para':
                    stream.pop()
                    stream.expect('.')
                    stream.pop()
                    stream.expect('=')
                    stream.pop()
                case 'self':
                    stat = ast_self.parse(stream)
                case 'return':
                    stat = ast_return.parse(stream)
                case 'break':
                    stat = ast_break.parse(stream)
                case 'continue':
                    stat = ast_continue.parse(stream)
                case 'repeat':
                    stat = ast_repeat.parse(stream, scope+1)

                case 'for':
                    stat = ast_for.parse(stream, scope+1)

                case x if x[0].isupper() and stream.peek() == '.':
                    stream.expect('.')
                    stream.expect('new')
                    stat = ast_call.parse(stream, constructer=x)

                case x if x[0].islower() and stream.peek() == '.':
                    stream.push(x)
                    stat = ast_method.parse(stream)
                
                case x:
                    stream.push(x)
                    stat = ast_call.parse(stream)

            if stat is not None:
                stats.append(stat)


            if stream.has() and stream.peek() == '\n':
                stream.expect('\n')

        return cls(stats) 




def main():
    path = sys.argv[1]

    with open(path, 'r') as f:
        src = f.read()

    stream = lex(src)
    root = ast_prog.parse(stream)
    root.run(env={
        "_fn" : {}, #functions
    })



if __name__ == '__main__':
    main()

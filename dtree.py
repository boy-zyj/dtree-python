# -*- coding: utf-8 -*-
import functools
from weakref import WeakKeyDictionary
from collections import OrderedDict

__version__ = "1.0.5"
__author__ = 'ZouYJ'

__all__ = (
    "Error",
    "UnknownPolicyError",
    "NoMatchError",
    "register_policy",
    "Description",
    "Condition",
    "And",
    "Or",
    "Not",
    "Else",
    "else_",
    "ELSE",
    "ToCondition",
    "Runner",
    "Catch",
    "Action",
    "ToAction",
    "Chain",
    "Node",
    "DTree",
    "ValueAccessor",
    "CachingGetter",
    "pass_",
    "PASS",
    "to_condition",
    "to_action",
    "isnode",
    "isaction",
    "iscondition",
    "isrunner",
    "isdtree",
)


class Error(Exception):
    pass


class UnknownPolicyError(Error):
    pass


class NoMatchError(Error):
    pass


def run_by_once_policy(self, obj):
    for condition, runner in self._condition_to_runner.items():
        if condition.validate(obj):
            return runner.run(obj)
    if self.else_runner:
        return self.else_runner.run(obj)
    else:
        raise NoMatchError


def run_by_recursive_policy(self, obj):
    for condition, runner in self._condition_to_runner.items():
        try:
            if condition.validate(obj):
                return runner.run(obj)
        except NoMatchError:
            continue
    if self.else_runner:
        return self.else_runner.run(obj)
    else:
        raise NoMatchError


ONCE = 'once'
RECURSIVE = 'recursive'
POLICIES = {
    ONCE: run_by_once_policy,
    RECURSIVE: run_by_recursive_policy,
}
DEFAULT_POLICY = ONCE


def register_policy(policy, run_method):
    global POLICIES
    assert policy not in POLICIES, 'Policy %s already registered' % policy
    POLICIES[policy] = run_method


class Description(object):

    _description = None

    @property
    def description(self):
        if self._description is None:
            self._description = self.get_default_description()
        return self._description

    @description.setter
    def description(self, description):
        self._description = description

    def get_default_description(self):
        return self.__class__.__name__


class Condition(Description):

    def validate(self, obj):
        raise NotImplementedError

    def __call__(self, obj):
        return self.validate(obj)

    def __or__(self, other):
        return Or(self, other)

    __ior__ = __or__

    def __and__(self, other):
        return And(self, other)

    __iand__ = __and__

    def __invert__(self):
        return Not(self)


class And(Condition):

    def __init__(self, *conditions):
        self._conditions = conditions

    def validate(self, obj):
        return all(condition.validate(obj) for condition in self._conditions)

    def get_default_description(self):
        L = [condition.description for condition in self._conditions]
        return 'AND(' + ', '.join(L) + ')'


class Or(Condition):

    def __init__(self, *conditions):
        self._conditions = conditions

    def validate(self, obj):
        return any(condition.validate(obj) for condition in self._conditions)

    def get_default_description(self):
        L = [condition.description for condition in self._conditions]
        return 'OR(' + ', '.join(L) + ')'


class Not(Condition):

    def __init__(self, condition):
        self._condition = condition

    def validate(self, obj):
        return not self._condition.validate(obj)

    def get_default_description(self):
        condition = self._condition
        n = 1
        while isinstance(condition, Not):
            n += 1
            condition = condition._condition
        if n % 2:
            return 'NOT(' + condition.description + ')'
        return condition.description


class Else(Condition):

    def validate(self, obj):
        return True

    def get_default_description(self):
        return "ELSE"


else_ = ELSE = Else()


class ToCondition(Condition):

    def __init__(self, validator, description=None):
        self._validator = validator
        if description is None and isinstance(validator, Condition):
            description = validator.description
        self._description = description

    def validate(self, obj):
        return self._validator(obj)


class Runner(Description):

    def run(self, obj):
        raise NotImplementedError

    def __div__(self, runner):
        assert isinstance(runner, Runner), "Expected Runner, got %s" % type(runner)
        return Chain(self, runner)

    __itruediv__ = __truediv__ = __idiv__ = __div__

    def then(self, next_runner):
        return Chain(self, next_runner)

    def catch(self, next_runner=None, error_handler=None):
        return Catch(self, next_runner, error_handler)

    def __call__(self, obj):
        return self.run(obj)


class Catch(Runner):

    def __init__(self, pre_runner, next_runner=None, error_handler=None):
        self.pre_runner = pre_runner
        self.next_runner = next_runner
        self.error_handler = error_handler

    def run(self, obj):
        try:
            return self.pre_runner.run(obj)
        except Exception as e:
            ret = None
            if self.next_runner:
                ret = self.next_runner.run(obj)
            if self.error_handler:
                self.error_handler(e, obj)
                return ret
            else:
                raise e

    def get_default_description(self):
        rv = "CATCH"
        if self.next_runner is not None:
            rv += " -> %s" % self.next_runner.description
        if self.error_handler is None:
            rv += " -> HANDLE"
        else:
            rv += ' -> THROW'
        return rv


class Action(Runner):
    pass


class ToAction(Action):

    def __init__(self, runner, description=None):
        self._runner = runner
        if description is None and isinstance(runner, Runner):
            description = runner.description
        self._description = description

    def run(self, obj):
        return self._runner(obj)


pass_ = PASS = ToAction(lambda obj: None, "PASS")


class Chain(Action):

    def __init__(self, *runners):
        for runner in runners:
            assert isinstance(runner, Runner)
        self._runners = runners

    def run(self, obj):
        ret = None
        for runner in self._runners:
            ret = runner.run(obj)
        return ret

    def get_default_description(self):
        return ' ==> '.join(runner.description for runner in self._runners)


class Node(object):

    def __init__(self, *args, **kwargs):
        for condition, runner_or_node in args:
            assert iscondition(condition), "Expected Condition, got %s" % type(condition)
            assert isrunner(runner_or_node) or isnode(runner_or_node), \
                "Expected Runner or Node, got %s" % type(runner_or_node)
        self.args = args
        self.kwargs = kwargs


class DTree(Runner):

    @property
    def depth(self):
        n = 0
        parent = self.parent
        while parent:
            n += 1
            parent = parent.parent
        return n

    @property
    def parent(self):
        if not hasattr(self, '_parent'):
            return None
        return self._parent

    @parent.setter
    def parent(self, parent):
        self._parent = parent

    def __init__(self, node):
        self._node = node
        kwargs = node.kwargs
        policy = kwargs.get('policy') or self.default_policy
        if policy is not None and policy not in POLICIES:
            raise UnknownPolicyError(policy)
        self._policy = policy
        self._condition_to_runner = OrderedDict()
        self._else_runner = None
        args = node.args
        for cond, run in args:
            self.add_child(cond, run)

    @property
    def node(self):
        return self._node

    @property
    def default_policy(self):
        return None

    @property
    def policy(self):
        if self.parent is None:
            return self._policy or DEFAULT_POLICY
        return self._policy or self.parent.policy

    def add_child(self, condition, runner_or_node):
        if isnode(runner_or_node):
            runner_or_node = self.__class__(runner_or_node)
            runner_or_node.parent = self
        elif not isinstance(runner_or_node, Runner):
            raise TypeError('Expected Node, Action or DTree object, got %s' % type(runner_or_node))
        if isinstance(condition, Else):
            assert self._else_runner is None, "Expected only one Else"
            self._else_runner = runner_or_node
        else:
            self._condition_to_runner[condition] = runner_or_node

    @property
    def children(self):
        if self.else_runner:
            return list(self._condition_to_runner.items()) + [(else_, self._else_runner)]
        return list(self._condition_to_runner.items())

    @property
    def else_runner(self):
        return self._else_runner

    def run(self, obj):
        run_method = POLICIES.get(self.policy)
        if run_method is None:
            raise UnknownPolicyError(self.policy)
        return run_method(self, obj)

    def __str__(self):
        rv = ''
        indent = '|      '
        dtree_mark = '+++'
        action_mark = '---'
        if self.depth == 0:
            policy_msg = self.policy != DEFAULT_POLICY and '(%s)' % self.policy or ''
            rv += dtree_mark + 'root%s:\n' % policy_msg
        for condition, runner in self.children:
            if isdtree(runner):
                policy_msg = runner.policy != DEFAULT_POLICY and '(%s)' % runner.policy or ''
                rv += indent * (self.depth + 1) + dtree_mark + condition.description + '%s:\n' % policy_msg
                rv += str(runner)
            elif isrunner(runner):
                rv += indent * (self.depth + 1) + action_mark + condition.description + ' --> ' + runner.description + '\n'
        return rv


def isnode(o):
    return isinstance(o, Node)


def isaction(o):
    return isinstance(o, Action)


def isrunner(o):
    return isinstance(o, Runner)


def iscondition(o):
    return isinstance(o, Condition)


def isdtree(o):
    return isinstance(o, DTree)


class CachingGetter:

    _SENTINEL = object()

    def __init__(self, getter):
        self._getter = getter
        self._cache = WeakKeyDictionary()

    def __call__(self, obj):
        ret = self._cache.get(obj, self._SENTINEL)
        if ret is self._SENTINEL:
            ret = self._getter(obj)
            self._cache[obj] = ret
        return ret


class ValueAccessor(object):

    def __init__(self, description, getter, caching=False):
        self._description = description
        if caching:
            getter = CachingGetter(getter)
        self._getter = getter

    def of(self, obj):
        return self._getter(obj)

    def _to_condition(self, validator, description=None):
        return ToCondition(validator, description)

    def eq(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) == other.of(obj),
                "%s = %s" % (self._description, other._description),
            )
        return self._to_condition(
            lambda obj: self.of(obj) == other,
            "%s = %s" % (self._description, other),
        )

    def lt(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) < other.of(obj),
                "%s < %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) < other, "%s < %s" % (self._description, other))

    def le(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) <= other.of(obj),
                "%s <= %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) <= other, "%s <= %s" % (self._description, other))

    def gt(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) > other.of(obj),
                "%s > %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) > other, "%s > %s" % (self._description, other))

    def ge(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) >= other.of(obj),
                "%s >= %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) >= other, "%s >= %s" % (self._description, other))

    def in_(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) in other.of(obj),
                "%s in %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) in other, "%s in %s" % (self._description, other))

    def is_(self, other):
        if isinstance(other, ValueAccessor):
            return self._to_condition(
                lambda obj: self.of(obj) is other.of(obj),
                "%s is %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) is other, "%s is %s" % (self._description, other))

    def test(self, validator, description=None):
        return self._to_condition(
            lambda obj: validator(self.of(obj)),
            description,
        )

    predicate = test

    def none(self):
        return self._to_condition(lambda obj: self.of(obj) is None, "%s is None" % self._description)

    def notnone(self):
        return self._to_condition(lambda obj: self.of(obj) is not None, "%s is not None" % self._description)

    def booltrue(self):
        return self._to_condition(lambda obj: bool(self.of(obj)), "%s is bool-true" % self._description)

    def boolfalse(self):
        return self._to_condition(lambda obj: not bool(self.of(obj)), "%s is bool-false" % self._description)


def to_condition(*args, **kwargs):

    def decorator(validator, description=None):
        return functools.wraps(validator)(
            ToCondition(
                validator,
                getattr(validator, '__name__', str(validator)) if description is None else description,
            )
        )

    if not args:
        description = kwargs.get('description')
        return functools.partial(decorator, description=description)

    elif len(args) == 1 and not kwargs:
        validator = args[0]
        return decorator(validator)
    else:
        raise ValueError("cannot combine positional and keyword args in to_condition")


def to_action(*args, **kwargs):

    def decorator(runner, description=None):
        return functools.wraps(runner)(
            ToAction(
                runner,
                getattr(runner, '__name__', str(runner)) if description is None else description,
            )
        )

    if not args:
        description = kwargs.get('description')
        return functools.partial(decorator, description=description)

    elif len(args) == 1 and not kwargs:
        runner = args[0]
        return decorator(runner)
    else:
        raise ValueError("cannot combine positional and keyword args in to_action")

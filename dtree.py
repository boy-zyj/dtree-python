# -*- coding: utf-8 -*-
from collections import OrderedDict

__version__ = "1.0.2"
__author__ = 'ZouYJ'


class Error(Exception):
    pass


class UnknownPolicyError(Error):
    pass


class NoMatchError(Error):
    pass


def run_by_once_policy(self, obj):
    for condition, runner in self._children.items():
        if condition.validate(obj):
            return runner.run(obj)
    if self.else_:
        return self.else_.run(obj)
    else:
        raise NoMatchError


def run_by_recursive_policy(self, obj):
    for condition, runner in self._children.items():
        try:
            if condition.validate(obj):
                return runner.run(obj)
        except NoMatchError:
            continue
    if self.else_:
        return self.else_.run(obj)
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


else_ = Else()


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

    __idiv__ = __div__
    __truediv__ = __div__

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


pass_ = ToAction(lambda obj: None, "PASS")


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
            assert is_condition(condition), "Expected Condition, got %s" % type(condition)
            assert is_runner(runner_or_node) or is_node(runner_or_node), \
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
        self._children = OrderedDict()
        self._else = None
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
        if is_node(runner_or_node):
            runner_or_node = self.__class__(runner_or_node)
            runner_or_node.parent = self
        elif not isinstance(runner_or_node, Runner):
            raise TypeError('Expected Node, Action or DTree object, got %s' % type(runner_or_node))
        if isinstance(condition, Else):
            assert self._else is None, "Expected only one Else"
            self._else = runner_or_node
        else:
            self._children[condition] = runner_or_node

    @property
    def children(self):
        if self.else_:
            return list(self._children.items()) + [(else_, self._else)]
        return list(self._children.items())

    @property
    def else_(self):
        return self._else

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
            if is_dtree(runner):
                policy_msg = runner.policy != DEFAULT_POLICY and '(%s)' % runner.policy or ''
                rv += indent * (self.depth + 1) + dtree_mark + condition.description + '%s:\n' % policy_msg
                rv += str(runner)
            elif is_runner(runner):
                rv += indent * (self.depth + 1) + action_mark + condition.description + ' --> ' + runner.description + '\n'
        return rv


def is_node(o):
    return isinstance(o, Node)


def is_action(o):
    return isinstance(o, Action)


def is_runner(o):
    return isinstance(o, Runner)


def is_condition(o):
    return isinstance(o, Condition)


def is_dtree(o):
    return isinstance(o, DTree)


class ValueGetter(object):

    def __init__(self, description, getter):
        self._description = description
        self._getter = getter

    def of(self, obj):
        return self._getter(obj)

    def _to_condition(self, validator, description=None):
        return ToCondition(validator, description)

    def eq(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) == other.of(obj),
                "%s = %s" % (self._description, other._description),
            )
        return self._to_condition(
            lambda obj: self.of(obj) == other,
            "%s = %s" % (self._description, other),
        )

    def lt(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) < other.of(obj),
                "%s < %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) < other, "%s < %s" % (self._description, other))

    def le(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) <= other.of(obj),
                "%s <= %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) <= other, "%s <= %s" % (self._description, other))

    def gt(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) > other.of(obj),
                "%s > %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) > other, "%s > %s" % (self._description, other))

    def ge(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) >= other.of(obj),
                "%s >= %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) >= other, "%s >= %s" % (self._description, other))

    def in_(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) in other.of(obj),
                "%s in %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) in other, "%s in %s" % (self._description, other))

    def is_(self, other):
        if isinstance(other, ValueGetter):
            return self._to_condition(
                lambda obj: self.of(obj) is other.of(obj),
                "%s is %s" % (self._description, other._description),
            )
        return self._to_condition(lambda obj: self.of(obj) is other, "%s is %s" % (self._description, other))

    def test(self, validator, description=None):
        return self._to_condition(validator, description)

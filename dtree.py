# -*- coding: utf-8 -*-
from collections import OrderedDict

__version__ = "1.0.0"
__author__ = 'YJ Zou'


class Error(Exception):
    pass


class UnknownPolicyError(Error):
    pass


class NoMatchError(Error):
    pass


def run_by_once_policy(self, obj):
    for cond, run in self._children.items():
        if cond.validate(obj):
            return run.run(obj)
    if self.else_:
        return self.else_.run(obj)
    else:
        raise NoMatchError


def run_by_repeat_policy(self, obj):
    for cond, run in self._children.items():
        try:
            if cond.validate(obj):
                return run.run(obj)
        except NoMatchError:
            continue
    if self.else_:
        return self.else_.run(obj)
    else:
        raise NoMatchError

ONCE = 'once'
REPEAT = 'repeat'
POLICIES = {
    ONCE: run_by_once_policy,
    REPEAT: run_by_repeat_policy,
}
DEFAULT_POLICY = ONCE


def register_policy(policy, run_method):
    global POLICIES
    assert policy not in POLICIES, 'Policy %s already registered' % policy
    POLICIES[policy] = run_method


class _Base(object):

    @property
    def description(self):
        return self.__class__.__name__


class Condition(_Base):

    @property
    def _unique(self):
        return id(self)

    def __hash__(self):
        return hash(self._unique)

    def __eq__(self, other):
        if not isinstance(other, Condition):
            return False
        return self._unique == other._unique

    def validate(self, obj):
        raise NotImplementedError

    def __or__(self, other):
        return Or(self, other)

    __ior__ = __or__

    def __and__(self, other):
        return And(self, other)

    __iand__ = __and__


class And(Condition):

    def __init__(self, *conds):
        self._conds = conds

    def validate(self, obj):
        return all(cond.validate(obj) for cond in self._conds)

    @property
    def _unique(self):
        _uniques = tuple([cond._unique for cond in self._conds])
        return (self.__class__,) + _uniques

    @property
    def description(self):
        desc_list = [cond.description for cond in self._conds]
        return 'AND(' + ', '.join(desc_list) + ')'


class Or(Condition):

    def __init__(self, *conds):
        self._conds = conds

    def validate(self, obj):
        return any(cond.validate(obj) for cond in self._conds)

    @property
    def _unique(self):
        _uniques = tuple([cond._unique for cond in self._conds])
        return (self.__class__,) + _uniques

    @property
    def description(self):
        desc_list = [cond.description for cond in self._conds]
        return 'OR(' + ', '.join(desc_list) + ')'


class Not(Condition):

    def __init__(self, cond):
        self._cond = cond

    @property
    def _unique(self):
        cond = self._cond
        n = 1
        while isinstance(cond, Not):
            n += 1
            cond = cond._cond
        if n % 2:
            return (self.__class__, cond._unique)
        return cond._unique

    def validate(self, obj):
        return not self._cond.validate(obj)

    @property
    def description(self):
        cond = self._cond
        n = 1
        while isinstance(cond, Not):
            n += 1
            cond = cond._cond
        if n % 2:
            return 'NOT(' + cond.description + ')'
        return cond.description


class Else(Condition):

    def validate(self, obj):
        return True

    def __eq__(self, other):
        return isinstance(other, Else)

    def __hash__(self):
        return id(Else)


else_ = Else()


class Runner(_Base):

    def run(self, obj):
        raise NotImplementedError

    def __div__(self, runner):
        assert isinstance(runner, Runner)
        runners = self.runners if isinstance(self, Chain) else (self,)
        runners += runner.runners if isinstance(runner, Chain) else (runner,)
        return Chain(*runners)

    __idiv__ = __div__

    def then(self, next_runner):
        return Chain(self, next_runner)

    def catch(self, next_runner=None, error_handle=None):
        return Capture(self, next_runner, error_handle)


class Capture(Runner):

    def __init__(self, pre_runner, next_runner=None, error_handle=None):
        self.pre_runner = pre_runner
        self.next_runner = next_runner
        self.error_handle = error_handle

    def run(self, obj):
        try:
            return self.pre_runner.run(obj)
        except Exception as e:
            if self.next_runner:
                ret = self.next_runner.run(obj)
            if self.error_handle:
                self.error_handle(obj, e)
                return ret
            else:
                raise e


class Action(Runner):
    pass


class Chain(Action):

    def __init__(self, *runners):
        for runner in runners:
            assert isinstance(runner, Runner)
        self.runners = runners

    def run(self, obj):
        ret = None
        for runner in self.runners:
            ret = runner.run(obj)
        return ret

    @property
    def description(self):
        return ' ==> '.join(runner.description for runner in self.runners)


class Node(object):

    def __init__(self, *args, **kwargs):
        for cond, run in args:
            assert is_condition(cond)
            assert (
                is_action(run) or
                is_node(run) or
                is_dtree(run)
            )
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

    def add_child(self, cond, run):
        if is_action(run):
            pass
        elif is_node(run):
            run = self.__class__(run)
        elif is_dtree(run):
            run = self.__class__(run.node)
        else:
            raise TypeError('Expected Node, Action or DTree object, got %s' % type(run))
        if isinstance(cond, Else):
            self._else = run
        else:
            self._children[cond] = run
        if is_dtree(run):
            run.parent = self

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
        for cond, run in self.children:
            if is_action(run):
                rv += indent * (self.depth + 1) + action_mark + cond.description + ' --> ' + run.description + '\n'
            elif is_dtree(run):
                policy_msg = run.policy != DEFAULT_POLICY and '(%s)' % run.policy or ''
                rv += indent * (self.depth + 1) + dtree_mark + cond.description + '%s:\n' % policy_msg
                rv += str(run)
        return rv


def is_node(o):
    return isinstance(o, Node)


def is_action(o):
    return isinstance(o, Action)


def is_condition(o):
    return isinstance(o, Condition)


def is_dtree(o):
    return isinstance(o, DTree)

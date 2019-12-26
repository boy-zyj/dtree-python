# -*- coding: utf-8 -*-
import unittest

from dtree import (
    Or,
    Not,
    And,
    ToAction,
    Condition,
    ValueGetter,
)

student = {
    'name': 'yao',
    'age': 18,
    'height': 170,
    'like': None,
}
name = ValueGetter('name', lambda s: s['name'])
age = ValueGetter('age', lambda s: s['age'])
like = ValueGetter('like', lambda s: s['like'])


class CommonTestCase(unittest.TestCase):

    def testValueGetter(self):
        self.assertEqual(name.of(student), 'yao')
        self.assertEqual(age.of(student), 18)
        self.assertTrue(age.eq(18).validate(student))
        self.assertTrue(age.gt(10).validate(student))
        self.assertTrue(age.ge(18).validate(student))
        self.assertTrue(age.ge(17).validate(student))
        self.assertTrue(age.lt(20).validate(student))
        self.assertTrue(age.le(18).validate(student))
        self.assertTrue(age.le(19).validate(student))
        self.assertTrue(age.in_([18, 20]).validate(student))
        self.assertTrue(like.is_(None).validate(student))
        self.assertEqual(age.eq(18).description, "age = 18")
        self.assertIsInstance(age.eq(18), Condition)

    def testCondition(self):
        self.assertTrue(And(name.eq('yao'), age.ge(18)).validate(student))
        self.assertFalse(age.gt(20).validate(student))
        self.assertTrue(Not(age.gt(20)).validate(student))
        self.assertTrue(Or(age.gt(20), name.eq('yao')).validate(student))
        self.assertTrue(
            (name.eq('yao') & age.ge(18)).validate(student)
        )
        self.assertTrue(
            (age.gt(20) | name.eq('yao')).validate(student)
        )
        self.assertTrue(
            (~age.gt(20)).validate(student)
        )
        self.assertTrue(
            (~age.gt(20) & name.eq('yao')).validate(student)
        )

    def testRunner(self):
        i = [0]

        def _add(s):
            i[0] += 1

        def _sub(s):
            i[0] -= 1

        add = ToAction(_add, "add 1")
        sub = ToAction(_sub, "sub 1")

        add.then(sub).then(add).run('')
        self.assertTrue(i[0] == 1)

        (add / sub / add).run('')
        self.assertTrue(i[0] == 2)

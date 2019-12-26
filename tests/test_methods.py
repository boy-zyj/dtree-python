# -*- coding: utf-8 -*-
import unittest

from dtree import (
    Or,
    Not,
    And,
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

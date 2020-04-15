# -*- coding: utf-8 -*-
import unittest

from dtree import *

student = {
    'name': 'yao',
    'age': 18,
    'height': 170,
    'like': None,
}
name = ValueAccessor('name', lambda s: s['name'])
age = ValueAccessor('age', lambda s: s['age'])
like = ValueAccessor('like', lambda s: s['like'])


class CommonTestCase(unittest.TestCase):

    def testValueAccessor(self):
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
        self.assertTrue(like.none().validate(student))
        self.assertTrue(name.notnone().validate(student))
        self.assertTrue(like.boolfalse().validate(student))
        self.assertTrue(name.booltrue().validate(student))

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

    def test_to_condition(self):

        @to_condition(description="18+")
        def is_adult(student):
            return student['age'] >= 18

        self.assertIsInstance(is_adult, Condition)
        self.assertTrue(is_adult.validate(student))
        self.assertEqual(is_adult.description, "18+")

    def test_to_action(self):

        @to_action(description="do nothing")
        def do_nothing(student):
            pass

        self.assertIsInstance(do_nothing, Runner)
        self.assertIsInstance(do_nothing, Action)
        self.assertTrue(do_nothing.run(student) is None)
        self.assertEqual(do_nothing.description, "do nothing")

    def test_usecache(self):

        class student:
            name = "yao"

        i = [0]

        def get_name(s):
            i[0] += 1
            return s.name

        name = ValueAccessor("name", get_name, cache=True)
        name.of(student)
        name.of(student)
        name.of(student)
        name.of(student)
        self.assertEqual(i[0], 1)

# -*- coding: utf-8 -*-
import textwrap
import unittest

from dtree import *

student = {
    'age': 15,
    'interest': 'reading',
    'gender': 'female',
}

age = ValueAccessor("age", lambda student: student['age'])
interest = ValueAccessor("interest", lambda student: student['interest'])
gender = ValueAccessor("gender", lambda student: student['gender'])

is_male = gender.eq("male")
is_female = gender.eq("female")


def give(item):
    return "give %s" % item


give_book = ToAction(lambda student: give("book"), "give book")
give_football = ToAction(lambda student: give("football"), "give football")
give_note = ToAction(lambda student: give("note"), "give note")


class DTreeTestCase(unittest.TestCase):

    def test(self):
        rule = DTree(Node(
            (age.lt(12), Node(
                (interest.eq("sports"), Node(
                    (is_female, give_note),
                    (else_, give_football),
                )),
                (else_, give_book),
            )),
            (age.ge(15), Node(
                (interest.eq("writing"), give_note),
                (else_, give_book),
            )),
            (else_, Node(
                (is_male, give_football),
                (else_, give_book),
            )),
        ))
        s = textwrap.dedent(
            """\
            +++root:
            |      +++age < 12:
            |      |      +++interest = sports:
            |      |      |      ---gender = female --> give note
            |      |      |      ---ELSE --> give football
            |      |      ---ELSE --> give book
            |      +++age >= 15:
            |      |      ---interest = writing --> give note
            |      |      ---ELSE --> give book
            |      +++ELSE:
            |      |      ---gender = male --> give football
            |      |      ---ELSE --> give book
            """
        )
        self.assertEqual(s, str(rule))
        gift = rule.run(student)  # give book
        self.assertEqual(gift, "give book")

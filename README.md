Flow-based process just got Pythonic
===============================================================================

**dtree** is a library for processing flow-based logical system with complicated
chain of if-else blocks just like handling a flowchart.

Example
----------------------------------------------------------------------------

Here is a quick example to get a feeling of **dtree**. Given information of a student like
```
student = {
    'age': 15,
    'interest': 'reading',
    'gender': 'female',
}
```
figure out what gift to give with the following logics:
```
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
```

```python
from dtree import *

student = {
    'age': 15,
    'interest': 'reading',
    'gender': 'female',
}

age = ValueGetter("age", lambda student: student['age'])
interest = ValueGetter("interest", lambda student: student['interest'])
gender = ValueGetter("gender", lambda student: student['gender'])

is_male = gender.eq("male")
is_female = gender.eq("female")


def give(item):
    print("give %s" % item)


give_book = ToAction(lambda student: give("book"), "give book")
give_football = ToAction(lambda student: give("football"), "give football")
give_note = ToAction(lambda student: give("note"), "give note")

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

rule.run(student)  # give book
```

Installation
-------------------------------------------------------------------------------

Use `pip <http://pip-installer.org>`_ or easy_install::

    pip install dtree-python

Alternatively, you can just drop ``dtree.py`` file into your project—it is
self-contained.

- **dtree** is tested with Python 2.6, 2.7, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7 and PyPy.

Exchange formats
================
Library exchanges with the client data in the formats described below.

Resource set
------------
Dictionary with keys are "options" and "ids".
On the key "options" is a dictionary of resource set options.
On the key "ids" is a list of resource id.
```python
{
  "options": {"id": "id"},
  "ids": ["resourceA", "resourceB"],
}
```

Constraint
----------
When constraint is plain (without resource sets) there is only dictionary with
constraint options.
```python
{"id": "id", "rsc": "resourceA"}
```

When is constraint with resource sets there is dictionary with keys
"resource_sets" and  "options".
On the key "options" is a dictionary of constraint options.
On the key "resource_sets" is a dictionary of resource sets (see Resource set).
```python
{
  "options": {"id": "id"},
  "resource_sets": {"options": {"id": "id"}, "ids": ["resourceA", "resourceB"]},
}
```

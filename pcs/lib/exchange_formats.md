Exchange formats
================
Library exchanges with the client data in the formats described below.

Resource operation interval duplication
---------------------------------------
Dictionary. Key is operation name. Value is list of list of interval.
```python
{
  "monitor": [
    ["3600s", "60m", "1h"],
    ["60s", "1m"],
  ],
},
```

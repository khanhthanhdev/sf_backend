# config_ops

Utilities that might be useful for configuration dictionaries.

### Classes

| [`DictAsObject`](manim.utils.config_ops.DictAsObject.md#manim.utils.config_ops.DictAsObject)   |    |
|------------------------------------------------------------------------------------------------|----|

### Functions

### merge_dicts_recursively(\*dicts)

Creates a dict whose keyset is the union of all the
input dictionaries.  The value for each key is based
on the first dict in the list with that key.

dicts later in the list have higher priority

When values are dictionaries, it is applied recursively

* **Parameters:**
  **dicts** (*dict* *[**Any* *,* *Any* *]*)
* **Return type:**
  dict[*Any*, *Any*]

### update_dict_recursively(current_dict, \*others)

* **Parameters:**
  * **current_dict** (*dict* *[**Any* *,* *Any* *]*)
  * **others** (*dict* *[**Any* *,* *Any* *]*)
* **Return type:**
  None

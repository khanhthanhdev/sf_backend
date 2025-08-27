# Underline

Qualified name: `manim.mobject.geometry.shape\_matchers.Underline`

### *class* Underline(mobject, buff=0.1, \*\*kwargs)

Bases: [`Line`](manim.mobject.geometry.line.Line.md#manim.mobject.geometry.line.Line)

Creates an underline.

### Examples

<div id="underline" class="admonition admonition-manim-example">
<p class="admonition-title">Example: UnderLine <a class="headerlink" href="#underline">¶</a></p>![image](media/images/UnderLine-1.png)
```python
from manim import *

class UnderLine(Scene):
    def construct(self):
        man = Tex("Manim")  # Full Word
        ul = Underline(man)  # Underlining the word
        self.add(man, ul)
```

<pre data-manim-binder data-manim-classname="UnderLine">
class UnderLine(Scene):
    def construct(self):
        man = Tex("Manim")  # Full Word
        ul = Underline(man)  # Underlining the word
        self.add(man, ul)

</pre></div>

### Methods

### Attributes

| `animate`             | Used to animate the application of any method of `self`.               |
|-----------------------|------------------------------------------------------------------------|
| `animation_overrides` |                                                                        |
| `color`               |                                                                        |
| `depth`               | The depth of the mobject.                                              |
| `fill_color`          | If there are multiple colors (for gradient) this returns the first one |
| `height`              | The height of the mobject.                                             |
| `n_points_per_curve`  |                                                                        |
| `sheen_factor`        |                                                                        |
| `stroke_color`        |                                                                        |
| `width`               | The width of the mobject.                                              |
* **Parameters:**
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject))
  * **buff** (*float*)
  * **kwargs** (*Any*)

#### \_original_\_init_\_(mobject, buff=0.1, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject))
  * **buff** (*float*)
  * **kwargs** (*Any*)
* **Return type:**
  None

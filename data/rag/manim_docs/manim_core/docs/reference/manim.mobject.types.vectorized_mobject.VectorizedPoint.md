# VectorizedPoint

Qualified name: `manim.mobject.types.vectorized\_mobject.VectorizedPoint`

### *class* VectorizedPoint(location=array([0., 0., 0.]), color=ManimColor('#000000'), fill_opacity=0, stroke_width=0, artificial_width=0.01, artificial_height=0.01, \*\*kwargs)

Bases: [`VMobject`](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject)

### Methods

| `get_location`   |    |
|------------------|----|
| `set_location`   |    |

### Attributes

| `animate`                                                                  | Used to animate the application of any method of `self`.               |
|----------------------------------------------------------------------------|------------------------------------------------------------------------|
| `animation_overrides`                                                      |                                                                        |
| `color`                                                                    |                                                                        |
| `depth`                                                                    | The depth of the mobject.                                              |
| `fill_color`                                                               | If there are multiple colors (for gradient) this returns the first one |
| [`height`](#manim.mobject.types.vectorized_mobject.VectorizedPoint.height) | The height of the mobject.                                             |
| `n_points_per_curve`                                                       |                                                                        |
| `sheen_factor`                                                             |                                                                        |
| `stroke_color`                                                             |                                                                        |
| [`width`](#manim.mobject.types.vectorized_mobject.VectorizedPoint.width)   | The width of the mobject.                                              |
* **Parameters:**
  * **location** ([*Point3DLike*](manim.typing.md#manim.typing.Point3DLike))
  * **color** ([*ManimColor*](manim.utils.color.core.ManimColor.md#manim.utils.color.core.ManimColor))
  * **fill_opacity** (*float*)
  * **stroke_width** (*float*)
  * **artificial_width** (*float*)
  * **artificial_height** (*float*)

#### \_original_\_init_\_(location=array([0., 0., 0.]), color=ManimColor('#000000'), fill_opacity=0, stroke_width=0, artificial_width=0.01, artificial_height=0.01, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **location** ([*Point3DLike*](manim.typing.md#manim.typing.Point3DLike))
  * **color** ([*ManimColor*](manim.utils.color.core.ManimColor.md#manim.utils.color.core.ManimColor))
  * **fill_opacity** (*float*)
  * **stroke_width** (*float*)
  * **artificial_width** (*float*)
  * **artificial_height** (*float*)
* **Return type:**
  None

#### basecls

alias of [`VMobject`](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject)

#### *property* height *: float*

The height of the mobject.

* **Return type:**
  `float`

### Examples

<div id="heightexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: HeightExample <a class="headerlink" href="#heightexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./HeightExample-2.mp4">
</video>
```python
from manim import *

class HeightExample(Scene):
    def construct(self):
        decimal = DecimalNumber().to_edge(UP)
        rect = Rectangle(color=BLUE)
        rect_copy = rect.copy().set_stroke(GRAY, opacity=0.5)

        decimal.add_updater(lambda d: d.set_value(rect.height))

        self.add(rect_copy, rect, decimal)
        self.play(rect.animate.set(height=5))
        self.wait()
```

<pre data-manim-binder data-manim-classname="HeightExample">
class HeightExample(Scene):
    def construct(self):
        decimal = DecimalNumber().to_edge(UP)
        rect = Rectangle(color=BLUE)
        rect_copy = rect.copy().set_stroke(GRAY, opacity=0.5)

        decimal.add_updater(lambda d: d.set_value(rect.height))

        self.add(rect_copy, rect, decimal)
        self.play(rect.animate.set(height=5))
        self.wait()

</pre></div>

#### SEE ALSO
`length_over_dim()`

#### *property* width *: float*

The width of the mobject.

* **Return type:**
  `float`

### Examples

<div id="widthexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: WidthExample <a class="headerlink" href="#widthexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./WidthExample-2.mp4">
</video>
```python
from manim import *

class WidthExample(Scene):
    def construct(self):
        decimal = DecimalNumber().to_edge(UP)
        rect = Rectangle(color=BLUE)
        rect_copy = rect.copy().set_stroke(GRAY, opacity=0.5)

        decimal.add_updater(lambda d: d.set_value(rect.width))

        self.add(rect_copy, rect, decimal)
        self.play(rect.animate.set(width=7))
        self.wait()
```

<pre data-manim-binder data-manim-classname="WidthExample">
class WidthExample(Scene):
    def construct(self):
        decimal = DecimalNumber().to_edge(UP)
        rect = Rectangle(color=BLUE)
        rect_copy = rect.copy().set_stroke(GRAY, opacity=0.5)

        decimal.add_updater(lambda d: d.set_value(rect.width))

        self.add(rect_copy, rect, decimal)
        self.play(rect.animate.set(width=7))
        self.wait()

</pre></div>

#### SEE ALSO
`length_over_dim()`

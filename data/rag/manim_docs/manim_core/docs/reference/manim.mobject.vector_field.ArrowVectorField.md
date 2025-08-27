# ArrowVectorField

Qualified name: `manim.mobject.vector\_field.ArrowVectorField`

### *class* ArrowVectorField(func, color=None, color_scheme=None, min_color_scheme_value=0, max_color_scheme_value=2, colors=[ManimColor('#236B8E'), ManimColor('#83C167'), ManimColor('#FFFF00'), ManimColor('#FC6255')], x_range=None, y_range=None, z_range=None, three_dimensions=False, length_func=<function ArrowVectorField.<lambda>>, opacity=1.0, vector_config=None, \*\*kwargs)

Bases: [`VectorField`](manim.mobject.vector_field.VectorField.md#manim.mobject.vector_field.VectorField)

A [`VectorField`](manim.mobject.vector_field.VectorField.md#manim.mobject.vector_field.VectorField) represented by a set of change vectors.

Vector fields are always based on a function defining the [`Vector`](manim.mobject.geometry.line.Vector.md#manim.mobject.geometry.line.Vector) at every position.
The values of this functions is displayed as a grid of vectors.
By default the color of each vector is determined by it’s magnitude.
Other color schemes can be used however.

* **Parameters:**
  * **func** (*Callable* *[* *[**np.ndarray* *]* *,* *np.ndarray* *]*) – The function defining the rate of change at every position of the vector field.
  * **color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *|* *None*) – The color of the vector field. If set, position-specific coloring is disabled.
  * **color_scheme** (*Callable* *[* *[**np.ndarray* *]* *,* *float* *]*  *|* *None*) – A function mapping a vector to a single value. This value gives the position in the color gradient defined using min_color_scheme_value, max_color_scheme_value and colors.
  * **min_color_scheme_value** (*float*) – The value of the color_scheme function to be mapped to the first color in colors. Lower values also result in the first color of the gradient.
  * **max_color_scheme_value** (*float*) – The value of the color_scheme function to be mapped to the last color in colors. Higher values also result in the last color of the gradient.
  * **colors** (*Sequence* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*) – The colors defining the color gradient of the vector field.
  * **x_range** (*Sequence* *[**float* *]*) – A sequence of x_min, x_max, delta_x
  * **y_range** (*Sequence* *[**float* *]*) – A sequence of y_min, y_max, delta_y
  * **z_range** (*Sequence* *[**float* *]*) – A sequence of z_min, z_max, delta_z
  * **three_dimensions** (*bool*) – Enables three_dimensions. Default set to False, automatically turns True if
    z_range is not None.
  * **length_func** (*Callable* *[* *[**float* *]* *,* *float* *]*) – The function determining the displayed size of the vectors. The actual size
    of the vector is passed, the returned value will be used as display size for the
    vector. By default this is used to cap the displayed size of vectors to reduce the clutter.
  * **opacity** (*float*) – The opacity of the arrows.
  * **vector_config** (*dict* *|* *None*) – Additional arguments to be passed to the [`Vector`](manim.mobject.geometry.line.Vector.md#manim.mobject.geometry.line.Vector) constructor
  * **kwargs** – Additional arguments to be passed to the [`VGroup`](manim.mobject.types.vectorized_mobject.VGroup.md#manim.mobject.types.vectorized_mobject.VGroup) constructor

### Examples

<div id="basicusage" class="admonition admonition-manim-example">
<p class="admonition-title">Example: BasicUsage <a class="headerlink" href="#basicusage">¶</a></p>![image](media/images/BasicUsage-1.png)
```python
from manim import *

class BasicUsage(Scene):
    def construct(self):
        func = lambda pos: ((pos[0] * UR + pos[1] * LEFT) - pos) / 3
        self.add(ArrowVectorField(func))
```

<pre data-manim-binder data-manim-classname="BasicUsage">
class BasicUsage(Scene):
    def construct(self):
        func = lambda pos: ((pos[0] \* UR + pos[1] \* LEFT) - pos) / 3
        self.add(ArrowVectorField(func))

</pre></div><div id="sizingandspacing" class="admonition admonition-manim-example">
<p class="admonition-title">Example: SizingAndSpacing <a class="headerlink" href="#sizingandspacing">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./SizingAndSpacing-1.mp4">
</video>
```python
from manim import *

class SizingAndSpacing(Scene):
    def construct(self):
        func = lambda pos: np.sin(pos[0] / 2) * UR + np.cos(pos[1] / 2) * LEFT
        vf = ArrowVectorField(func, x_range=[-7, 7, 1])
        self.add(vf)
        self.wait()

        length_func = lambda x: x / 3
        vf2 = ArrowVectorField(func, x_range=[-7, 7, 1], length_func=length_func)
        self.play(vf.animate.become(vf2))
        self.wait()
```

<pre data-manim-binder data-manim-classname="SizingAndSpacing">
class SizingAndSpacing(Scene):
    def construct(self):
        func = lambda pos: np.sin(pos[0] / 2) \* UR + np.cos(pos[1] / 2) \* LEFT
        vf = ArrowVectorField(func, x_range=[-7, 7, 1])
        self.add(vf)
        self.wait()

        length_func = lambda x: x / 3
        vf2 = ArrowVectorField(func, x_range=[-7, 7, 1], length_func=length_func)
        self.play(vf.animate.become(vf2))
        self.wait()

</pre></div><div id="coloring" class="admonition admonition-manim-example">
<p class="admonition-title">Example: Coloring <a class="headerlink" href="#coloring">¶</a></p>![image](media/images/Coloring-1.png)
```python
from manim import *

class Coloring(Scene):
    def construct(self):
        func = lambda pos: pos - LEFT * 5
        colors = [RED, YELLOW, BLUE, DARK_GRAY]
        min_radius = Circle(radius=2, color=colors[0]).shift(LEFT * 5)
        max_radius = Circle(radius=10, color=colors[-1]).shift(LEFT * 5)
        vf = ArrowVectorField(
            func, min_color_scheme_value=2, max_color_scheme_value=10, colors=colors
        )
        self.add(vf, min_radius, max_radius)
```

<pre data-manim-binder data-manim-classname="Coloring">
class Coloring(Scene):
    def construct(self):
        func = lambda pos: pos - LEFT \* 5
        colors = [RED, YELLOW, BLUE, DARK_GRAY]
        min_radius = Circle(radius=2, color=colors[0]).shift(LEFT \* 5)
        max_radius = Circle(radius=10, color=colors[-1]).shift(LEFT \* 5)
        vf = ArrowVectorField(
            func, min_color_scheme_value=2, max_color_scheme_value=10, colors=colors
        )
        self.add(vf, min_radius, max_radius)

</pre></div>

### Methods

| [`get_vector`](#manim.mobject.vector_field.ArrowVectorField.get_vector)   | Creates a vector in the vector field.   |
|---------------------------------------------------------------------------|-----------------------------------------|

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

#### \_original_\_init_\_(func, color=None, color_scheme=None, min_color_scheme_value=0, max_color_scheme_value=2, colors=[ManimColor('#236B8E'), ManimColor('#83C167'), ManimColor('#FFFF00'), ManimColor('#FC6255')], x_range=None, y_range=None, z_range=None, three_dimensions=False, length_func=<function ArrowVectorField.<lambda>>, opacity=1.0, vector_config=None, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **func** (*Callable* *[* *[**np.ndarray* *]* *,* *np.ndarray* *]*)
  * **color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *|* *None*)
  * **color_scheme** (*Callable* *[* *[**np.ndarray* *]* *,* *float* *]*  *|* *None*)
  * **min_color_scheme_value** (*float*)
  * **max_color_scheme_value** (*float*)
  * **colors** (*Sequence* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*)
  * **x_range** (*Sequence* *[**float* *]*)
  * **y_range** (*Sequence* *[**float* *]*)
  * **z_range** (*Sequence* *[**float* *]*)
  * **three_dimensions** (*bool*)
  * **length_func** (*Callable* *[* *[**float* *]* *,* *float* *]*)
  * **opacity** (*float*)
  * **vector_config** (*dict* *|* *None*)

#### get_vector(point)

Creates a vector in the vector field.

The created vector is based on the function of the vector field and is
rooted in the given point. Color and length fit the specifications of
this vector field.

* **Parameters:**
  **point** (*ndarray*) – The root point of the vector.

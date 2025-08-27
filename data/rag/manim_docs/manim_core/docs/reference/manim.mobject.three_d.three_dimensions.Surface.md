# Surface

Qualified name: `manim.mobject.three\_d.three\_dimensions.Surface`

### *class* Surface(func, u_range=[0, 1], v_range=[0, 1], resolution=32, surface_piece_config={}, fill_color=ManimColor('#29ABCA'), fill_opacity=1.0, checkerboard_colors=[ManimColor('#29ABCA'), ManimColor('#236B8E')], stroke_color=ManimColor('#BBBBBB'), stroke_width=0.5, should_make_jagged=False, pre_function_handle_to_anchor_scale_factor=1e-05, \*\*kwargs)

Bases: [`VGroup`](manim.mobject.types.vectorized_mobject.VGroup.md#manim.mobject.types.vectorized_mobject.VGroup)

Creates a Parametric Surface using a checkerboard pattern.

* **Parameters:**
  * **func** (*Callable* *[* *[**float* *,* *float* *]* *,* *np.ndarray* *]*) – The function defining the [`Surface`](#manim.mobject.three_d.three_dimensions.Surface).
  * **u_range** (*Sequence* *[**float* *]*) – The range of the `u` variable: `(u_min, u_max)`.
  * **v_range** (*Sequence* *[**float* *]*) – The range of the `v` variable: `(v_min, v_max)`.
  * **resolution** (*Sequence* *[**int* *]*) – The number of samples taken of the [`Surface`](#manim.mobject.three_d.three_dimensions.Surface). A tuple can be
    used to define different resolutions for `u` and `v` respectively.
  * **fill_color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor)) – The color of the [`Surface`](#manim.mobject.three_d.three_dimensions.Surface). Ignored if `checkerboard_colors`
    is set.
  * **fill_opacity** (*float*) – The opacity of the [`Surface`](#manim.mobject.three_d.three_dimensions.Surface), from 0 being fully transparent
    to 1 being fully opaque. Defaults to 1.
  * **checkerboard_colors** (*Sequence* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*  *|* *bool*) – ng individual faces alternating colors. Overrides `fill_color`.
  * **stroke_color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor)) – Color of the stroke surrounding each face of [`Surface`](#manim.mobject.three_d.three_dimensions.Surface).
  * **stroke_width** (*float*) – Width of the stroke surrounding each face of [`Surface`](#manim.mobject.three_d.three_dimensions.Surface).
    Defaults to 0.5.
  * **should_make_jagged** (*bool*) – Changes the anchor mode of the Bézier curves from smooth to jagged.
    Defaults to `False`.
  * **surface_piece_config** (*dict*)
  * **pre_function_handle_to_anchor_scale_factor** (*float*)
  * **kwargs** (*Any*)

### Examples

<div id="parasurface" class="admonition admonition-manim-example">
<p class="admonition-title">Example: ParaSurface <a class="headerlink" href="#parasurface">¶</a></p>![image](media/images/ParaSurface-1.png)
```python
from manim import *

class ParaSurface(ThreeDScene):
    def func(self, u, v):
        return np.array([np.cos(u) * np.cos(v), np.cos(u) * np.sin(v), u])

    def construct(self):
        axes = ThreeDAxes(x_range=[-4,4], x_length=8)
        surface = Surface(
            lambda u, v: axes.c2p(*self.func(u, v)),
            u_range=[-PI, PI],
            v_range=[0, TAU],
            resolution=8,
        )
        self.set_camera_orientation(theta=70 * DEGREES, phi=75 * DEGREES)
        self.add(axes, surface)
```

<pre data-manim-binder data-manim-classname="ParaSurface">
class ParaSurface(ThreeDScene):
    def func(self, u, v):
        return np.array([np.cos(u) \* np.cos(v), np.cos(u) \* np.sin(v), u])

    def construct(self):
        axes = ThreeDAxes(x_range=[-4,4], x_length=8)
        surface = Surface(
            lambda u, v: axes.c2p(\*self.func(u, v)),
            u_range=[-PI, PI],
            v_range=[0, TAU],
            resolution=8,
        )
        self.set_camera_orientation(theta=70 \* DEGREES, phi=75 \* DEGREES)
        self.add(axes, surface)

</pre></div>

### Methods

| `func`                                                                                                 |                                                                                                                             |
|--------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| [`set_fill_by_checkerboard`](#manim.mobject.three_d.three_dimensions.Surface.set_fill_by_checkerboard) | Sets the fill_color of each face of [`Surface`](#manim.mobject.three_d.three_dimensions.Surface) in an alternating pattern. |
| [`set_fill_by_value`](#manim.mobject.three_d.three_dimensions.Surface.set_fill_by_value)               | Sets the color of each mobject of a parametric surface to a color relative to its axis-value.                               |

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

#### \_original_\_init_\_(func, u_range=[0, 1], v_range=[0, 1], resolution=32, surface_piece_config={}, fill_color=ManimColor('#29ABCA'), fill_opacity=1.0, checkerboard_colors=[ManimColor('#29ABCA'), ManimColor('#236B8E')], stroke_color=ManimColor('#BBBBBB'), stroke_width=0.5, should_make_jagged=False, pre_function_handle_to_anchor_scale_factor=1e-05, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **func** (*Callable* *[* *[**float* *,* *float* *]* *,* *ndarray* *]*)
  * **u_range** (*Sequence* *[**float* *]*)
  * **v_range** (*Sequence* *[**float* *]*)
  * **resolution** (*Sequence* *[**int* *]*)
  * **surface_piece_config** (*dict*)
  * **fill_color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor))
  * **fill_opacity** (*float*)
  * **checkerboard_colors** (*Sequence* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*  *|* *bool*)
  * **stroke_color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor))
  * **stroke_width** (*float*)
  * **should_make_jagged** (*bool*)
  * **pre_function_handle_to_anchor_scale_factor** (*float*)
  * **kwargs** (*Any*)
* **Return type:**
  None

#### set_fill_by_checkerboard(\*colors, opacity=None)

Sets the fill_color of each face of [`Surface`](#manim.mobject.three_d.three_dimensions.Surface) in
an alternating pattern.

* **Parameters:**
  * **colors** (*Iterable* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*) – List of colors for alternating pattern.
  * **opacity** (*float* *|* *None*) – The fill_opacity of [`Surface`](#manim.mobject.three_d.three_dimensions.Surface), from 0 being fully transparent
    to 1 being fully opaque.
* **Returns:**
  The parametric surface with an alternating pattern.
* **Return type:**
  [`Surface`](#manim.mobject.three_d.three_dimensions.Surface)

#### set_fill_by_value(axes, colorscale=None, axis=2, \*\*kwargs)

Sets the color of each mobject of a parametric surface to a color
relative to its axis-value.

* **Parameters:**
  * **axes** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The axes for the parametric surface, which will be used to map
    axis-values to colors.
  * **colorscale** (*list* *[*[*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *]*  *|* [*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *|* *None*) – A list of colors, ordered from lower axis-values to higher axis-values.
    If a list of tuples is passed containing colors paired with numbers,
    then those numbers will be used as the pivots.
  * **axis** (*int*) – The chosen axis to use for the color mapping. (0 = x, 1 = y, 2 = z)
* **Returns:**
  The parametric surface with a gradient applied by value. For chaining.
* **Return type:**
  [`Surface`](#manim.mobject.three_d.three_dimensions.Surface)

### Examples

<div id="fillbyvalueexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: FillByValueExample <a class="headerlink" href="#fillbyvalueexample">¶</a></p>![image](media/images/FillByValueExample-1.png)
```python
from manim import *

class FillByValueExample(ThreeDScene):
    def construct(self):
        resolution_fa = 8
        self.set_camera_orientation(phi=75 * DEGREES, theta=-160 * DEGREES)
        axes = ThreeDAxes(x_range=(0, 5, 1), y_range=(0, 5, 1), z_range=(-1, 1, 0.5))
        def param_surface(u, v):
            x = u
            y = v
            z = np.sin(x) * np.cos(y)
            return z
        surface_plane = Surface(
            lambda u, v: axes.c2p(u, v, param_surface(u, v)),
            resolution=(resolution_fa, resolution_fa),
            v_range=[0, 5],
            u_range=[0, 5],
            )
        surface_plane.set_style(fill_opacity=1)
        surface_plane.set_fill_by_value(axes=axes, colorscale=[(RED, -0.5), (YELLOW, 0), (GREEN, 0.5)], axis=2)
        self.add(axes, surface_plane)
```

<pre data-manim-binder data-manim-classname="FillByValueExample">
class FillByValueExample(ThreeDScene):
    def construct(self):
        resolution_fa = 8
        self.set_camera_orientation(phi=75 \* DEGREES, theta=-160 \* DEGREES)
        axes = ThreeDAxes(x_range=(0, 5, 1), y_range=(0, 5, 1), z_range=(-1, 1, 0.5))
        def param_surface(u, v):
            x = u
            y = v
            z = np.sin(x) \* np.cos(y)
            return z
        surface_plane = Surface(
            lambda u, v: axes.c2p(u, v, param_surface(u, v)),
            resolution=(resolution_fa, resolution_fa),
            v_range=[0, 5],
            u_range=[0, 5],
            )
        surface_plane.set_style(fill_opacity=1)
        surface_plane.set_fill_by_value(axes=axes, colorscale=[(RED, -0.5), (YELLOW, 0), (GREEN, 0.5)], axis=2)
        self.add(axes, surface_plane)

</pre></div>

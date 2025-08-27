# ThreeDAxes

Qualified name: `manim.mobject.graphing.coordinate\_systems.ThreeDAxes`

### *class* ThreeDAxes(x_range=(-6, 6, 1), y_range=(-5, 5, 1), z_range=(-4, 4, 1), x_length=10.5, y_length=10.5, z_length=6.5, z_axis_config=None, z_normal=array([0., -1., 0.]), num_axis_pieces=20, light_source=array([-7., -9., 10.]), depth=None, gloss=0.5, \*\*kwargs)

Bases: [`Axes`](manim.mobject.graphing.coordinate_systems.Axes.md#manim.mobject.graphing.coordinate_systems.Axes)

A 3-dimensional set of axes.

* **Parameters:**
  * **x_range** (*Sequence* *[**float* *]*  *|* *None*) – The `[x_min, x_max, x_step]` values of the x-axis.
  * **y_range** (*Sequence* *[**float* *]*  *|* *None*) – The `[y_min, y_max, y_step]` values of the y-axis.
  * **z_range** (*Sequence* *[**float* *]*  *|* *None*) – The `[z_min, z_max, z_step]` values of the z-axis.
  * **x_length** (*float* *|* *None*) – The length of the x-axis.
  * **y_length** (*float* *|* *None*) – The length of the y-axis.
  * **z_length** (*float* *|* *None*) – The length of the z-axis.
  * **z_axis_config** (*dict* *[**str* *,* *Any* *]*  *|* *None*) – Arguments to be passed to [`NumberLine`](manim.mobject.graphing.number_line.NumberLine.md#manim.mobject.graphing.number_line.NumberLine) that influence the z-axis.
  * **z_normal** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The direction of the normal.
  * **num_axis_pieces** (*int*) – The number of pieces used to construct the axes.
  * **light_source** (*Sequence* *[**float* *]*) – The direction of the light source.
  * **depth** – Currently non-functional.
  * **gloss** – Currently non-functional.
  * **kwargs** (*dict* *[**str* *,* *Any* *]*) – Additional arguments to be passed to [`Axes`](manim.mobject.graphing.coordinate_systems.Axes.md#manim.mobject.graphing.coordinate_systems.Axes).

### Methods

| [`get_axis_labels`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_axis_labels)   | Defines labels for the x_axis and y_axis of the graph.   |
|----------------------------------------------------------------------------------------------|----------------------------------------------------------|
| [`get_y_axis_label`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_y_axis_label) | Generate a y-axis label.                                 |
| [`get_z_axis_label`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_z_axis_label) | Generate a z-axis label.                                 |

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

#### \_original_\_init_\_(x_range=(-6, 6, 1), y_range=(-5, 5, 1), z_range=(-4, 4, 1), x_length=10.5, y_length=10.5, z_length=6.5, z_axis_config=None, z_normal=array([0., -1., 0.]), num_axis_pieces=20, light_source=array([-7., -9., 10.]), depth=None, gloss=0.5, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **x_range** (*Sequence* *[**float* *]*  *|* *None*)
  * **y_range** (*Sequence* *[**float* *]*  *|* *None*)
  * **z_range** (*Sequence* *[**float* *]*  *|* *None*)
  * **x_length** (*float* *|* *None*)
  * **y_length** (*float* *|* *None*)
  * **z_length** (*float* *|* *None*)
  * **z_axis_config** (*dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **z_normal** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D))
  * **num_axis_pieces** (*int*)
  * **light_source** (*Sequence* *[**float* *]*)
  * **kwargs** (*dict* *[**str* *,* *Any* *]*)
* **Return type:**
  None

#### get_axis_labels(x_label='x', y_label='y', z_label='z')

Defines labels for the x_axis and y_axis of the graph.

For increased control over the position of the labels,
use [`get_x_axis_label()`](manim.mobject.graphing.coordinate_systems.CoordinateSystem.md#manim.mobject.graphing.coordinate_systems.CoordinateSystem.get_x_axis_label),
[`get_y_axis_label()`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_y_axis_label), and
[`get_z_axis_label()`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_z_axis_label).

* **Parameters:**
  * **x_label** (*float* *|* *str* *|* [*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The label for the x_axis. Defaults to [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex) for `str` and `float` inputs.
  * **y_label** (*float* *|* *str* *|* [*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The label for the y_axis. Defaults to [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex) for `str` and `float` inputs.
  * **z_label** (*float* *|* *str* *|* [*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The label for the z_axis. Defaults to [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex) for `str` and `float` inputs.
* **Returns:**
  A [`VGroup`](manim.mobject.types.vectorized_mobject.VGroup.md#manim.mobject.types.vectorized_mobject.VGroup) of the labels for the x_axis, y_axis, and z_axis.
* **Return type:**
  [`VGroup`](manim.mobject.types.vectorized_mobject.VGroup.md#manim.mobject.types.vectorized_mobject.VGroup)

#### SEE ALSO
[`get_x_axis_label()`](manim.mobject.graphing.coordinate_systems.CoordinateSystem.md#manim.mobject.graphing.coordinate_systems.CoordinateSystem.get_x_axis_label)
[`get_y_axis_label()`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_y_axis_label)
[`get_z_axis_label()`](#manim.mobject.graphing.coordinate_systems.ThreeDAxes.get_z_axis_label)

### Examples

<div id="getaxislabelsexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: GetAxisLabelsExample <a class="headerlink" href="#getaxislabelsexample">¶</a></p>![image](media/images/GetAxisLabelsExample-2.png)
```python
from manim import *

class GetAxisLabelsExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=2*PI/5, theta=PI/5)
        axes = ThreeDAxes()
        labels = axes.get_axis_labels(
            Text("x-axis").scale(0.7), Text("y-axis").scale(0.45), Text("z-axis").scale(0.45)
        )
        self.add(axes, labels)
```

<pre data-manim-binder data-manim-classname="GetAxisLabelsExample">
class GetAxisLabelsExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=2\*PI/5, theta=PI/5)
        axes = ThreeDAxes()
        labels = axes.get_axis_labels(
            Text("x-axis").scale(0.7), Text("y-axis").scale(0.45), Text("z-axis").scale(0.45)
        )
        self.add(axes, labels)

</pre></div>

#### get_y_axis_label(label, edge=array([1., 1., 0.]), direction=array([1., 1., 0.]), buff=0.1, rotation=1.5707963267948966, rotation_axis=array([0., 0., 1.]), \*\*kwargs)

Generate a y-axis label.

* **Parameters:**
  * **label** (*float* *|* *str* *|* [*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The label. Defaults to [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex) for `str` and `float` inputs.
  * **edge** (*Sequence* *[**float* *]*) – The edge of the y-axis to which the label will be added, by default `UR`.
  * **direction** (*Sequence* *[**float* *]*) – Allows for further positioning of the label from an edge, by default `UR`.
  * **buff** (*float*) – The distance of the label from the line, by default `SMALL_BUFF`.
  * **rotation** (*float*) – The angle at which to rotate the label, by default `PI/2`.
  * **rotation_axis** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The axis about which to rotate the label, by default `OUT`.
* **Returns:**
  The positioned label.
* **Return type:**
  [`Mobject`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)

### Examples

<div id="getyaxislabelexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: GetYAxisLabelExample <a class="headerlink" href="#getyaxislabelexample">¶</a></p>![image](media/images/GetYAxisLabelExample-2.png)
```python
from manim import *

class GetYAxisLabelExample(ThreeDScene):
    def construct(self):
        ax = ThreeDAxes()
        lab = ax.get_y_axis_label(Tex("$y$-label"))
        self.set_camera_orientation(phi=2*PI/5, theta=PI/5)
        self.add(ax, lab)
```

<pre data-manim-binder data-manim-classname="GetYAxisLabelExample">
class GetYAxisLabelExample(ThreeDScene):
    def construct(self):
        ax = ThreeDAxes()
        lab = ax.get_y_axis_label(Tex("$y$-label"))
        self.set_camera_orientation(phi=2\*PI/5, theta=PI/5)
        self.add(ax, lab)

</pre></div>

#### get_z_axis_label(label, edge=array([0., 0., 1.]), direction=array([1., 0., 0.]), buff=0.1, rotation=1.5707963267948966, rotation_axis=array([1., 0., 0.]), \*\*kwargs)

Generate a z-axis label.

* **Parameters:**
  * **label** (*float* *|* *str* *|* [*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The label. Defaults to [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex) for `str` and `float` inputs.
  * **edge** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The edge of the z-axis to which the label will be added, by default `OUT`.
  * **direction** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – Allows for further positioning of the label from an edge, by default `RIGHT`.
  * **buff** (*float*) – The distance of the label from the line, by default `SMALL_BUFF`.
  * **rotation** (*float*) – The angle at which to rotate the label, by default `PI/2`.
  * **rotation_axis** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The axis about which to rotate the label, by default `RIGHT`.
  * **kwargs** (*Any*)
* **Returns:**
  The positioned label.
* **Return type:**
  [`Mobject`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)

### Examples

<div id="getzaxislabelexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: GetZAxisLabelExample <a class="headerlink" href="#getzaxislabelexample">¶</a></p>![image](media/images/GetZAxisLabelExample-1.png)
```python
from manim import *

class GetZAxisLabelExample(ThreeDScene):
    def construct(self):
        ax = ThreeDAxes()
        lab = ax.get_z_axis_label(Tex("$z$-label"))
        self.set_camera_orientation(phi=2*PI/5, theta=PI/5)
        self.add(ax, lab)
```

<pre data-manim-binder data-manim-classname="GetZAxisLabelExample">
class GetZAxisLabelExample(ThreeDScene):
    def construct(self):
        ax = ThreeDAxes()
        lab = ax.get_z_axis_label(Tex("$z$-label"))
        self.set_camera_orientation(phi=2\*PI/5, theta=PI/5)
        self.add(ax, lab)

</pre></div>

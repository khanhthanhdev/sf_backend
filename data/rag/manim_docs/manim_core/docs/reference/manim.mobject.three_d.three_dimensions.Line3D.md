# Line3D

Qualified name: `manim.mobject.three\_d.three\_dimensions.Line3D`

### *class* Line3D(start=array([-1., 0., 0.]), end=array([1., 0., 0.]), thickness=0.02, color=None, resolution=24, \*\*kwargs)

Bases: [`Cylinder`](manim.mobject.three_d.three_dimensions.Cylinder.md#manim.mobject.three_d.three_dimensions.Cylinder)

A cylindrical line, for use in ThreeDScene.

* **Parameters:**
  * **start** (*np.ndarray*) – The start point of the line.
  * **end** (*np.ndarray*) – The end point of the line.
  * **thickness** (*float*) – The thickness of the line.
  * **color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *|* *None*) – The color of the line.
  * **resolution** (*int* *|* *Sequence* *[**int* *]*) – The resolution of the line.
    By default this value is the number of points the line will sampled at.
    If you want the line to also come out checkered, use a tuple.
    For example, for a line made of 24 points with 4 checker points on each
    cylinder, pass the tuple (4, 24).

### Examples

<div id="exampleline3d" class="admonition admonition-manim-example">
<p class="admonition-title">Example: ExampleLine3D <a class="headerlink" href="#exampleline3d">¶</a></p>![image](media/images/ExampleLine3D-1.png)
```python
from manim import *

class ExampleLine3D(ThreeDScene):
    def construct(self):
        axes = ThreeDAxes()
        line = Line3D(start=np.array([0, 0, 0]), end=np.array([2, 2, 2]))
        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)
        self.add(axes, line)
```

<pre data-manim-binder data-manim-classname="ExampleLine3D">
class ExampleLine3D(ThreeDScene):
    def construct(self):
        axes = ThreeDAxes()
        line = Line3D(start=np.array([0, 0, 0]), end=np.array([2, 2, 2]))
        self.set_camera_orientation(phi=75 \* DEGREES, theta=30 \* DEGREES)
        self.add(axes, line)

</pre></div>

### Methods

| [`get_end`](#manim.mobject.three_d.three_dimensions.Line3D.get_end)                                 | Returns the ending point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).                               |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [`get_start`](#manim.mobject.three_d.three_dimensions.Line3D.get_start)                             | Returns the starting point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).                             |
| [`parallel_to`](#manim.mobject.three_d.three_dimensions.Line3D.parallel_to)                         | Returns a line parallel to another line going through a given point.                                                      |
| [`perpendicular_to`](#manim.mobject.three_d.three_dimensions.Line3D.perpendicular_to)               | Returns a line perpendicular to another line going through a given point.                                                 |
| [`pointify`](#manim.mobject.three_d.three_dimensions.Line3D.pointify)                               | Gets a point representing the center of the [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject). |
| [`set_start_and_end_attrs`](#manim.mobject.three_d.three_dimensions.Line3D.set_start_and_end_attrs) | Sets the start and end points of the line.                                                                                |

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

#### \_original_\_init_\_(start=array([-1., 0., 0.]), end=array([1., 0., 0.]), thickness=0.02, color=None, resolution=24, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **start** (*np.ndarray*)
  * **end** (*np.ndarray*)
  * **thickness** (*float*)
  * **color** ([*ParsableManimColor*](manim.utils.color.core.md#manim.utils.color.core.ParsableManimColor) *|* *None*)
  * **resolution** (*int* *|* *Sequence* *[**int* *]*)

#### get_end()

Returns the ending point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).

* **Returns:**
  **end** – Ending point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).
* **Return type:**
  `numpy.array`

#### get_start()

Returns the starting point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).

* **Returns:**
  **start** – Starting point of the [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D).
* **Return type:**
  `numpy.array`

#### *classmethod* parallel_to(line, point=array([0., 0., 0.]), length=5, \*\*kwargs)

Returns a line parallel to another line going through
a given point.

* **Parameters:**
  * **line** ([*Line3D*](#manim.mobject.three_d.three_dimensions.Line3D)) – The line to be parallel to.
  * **point** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The point to pass through.
  * **length** (*float*) – Length of the parallel line.
  * **kwargs** – Additional parameters to be passed to the class.
* **Returns:**
  Line parallel to `line`.
* **Return type:**
  [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D)

### Examples

<div id="parallellineexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: ParallelLineExample <a class="headerlink" href="#parallellineexample">¶</a></p>![image](media/images/ParallelLineExample-1.png)
```python
from manim import *

class ParallelLineExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(PI / 3, -PI / 4)
        ax = ThreeDAxes((-5, 5), (-5, 5), (-5, 5), 10, 10, 10)
        line1 = Line3D(RIGHT * 2, UP + OUT, color=RED)
        line2 = Line3D.parallel_to(line1, color=YELLOW)
        self.add(ax, line1, line2)
```

<pre data-manim-binder data-manim-classname="ParallelLineExample">
class ParallelLineExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(PI / 3, -PI / 4)
        ax = ThreeDAxes((-5, 5), (-5, 5), (-5, 5), 10, 10, 10)
        line1 = Line3D(RIGHT \* 2, UP + OUT, color=RED)
        line2 = Line3D.parallel_to(line1, color=YELLOW)
        self.add(ax, line1, line2)

</pre></div>

#### *classmethod* perpendicular_to(line, point=array([0., 0., 0.]), length=5, \*\*kwargs)

Returns a line perpendicular to another line going through
a given point.

* **Parameters:**
  * **line** ([*Line3D*](#manim.mobject.three_d.three_dimensions.Line3D)) – The line to be perpendicular to.
  * **point** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – The point to pass through.
  * **length** (*float*) – Length of the perpendicular line.
  * **kwargs** – Additional parameters to be passed to the class.
* **Returns:**
  Line perpendicular to `line`.
* **Return type:**
  [`Line3D`](#manim.mobject.three_d.three_dimensions.Line3D)

### Examples

<div id="perplineexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: PerpLineExample <a class="headerlink" href="#perplineexample">¶</a></p>![image](media/images/PerpLineExample-1.png)
```python
from manim import *

class PerpLineExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(PI / 3, -PI / 4)
        ax = ThreeDAxes((-5, 5), (-5, 5), (-5, 5), 10, 10, 10)
        line1 = Line3D(RIGHT * 2, UP + OUT, color=RED)
        line2 = Line3D.perpendicular_to(line1, color=BLUE)
        self.add(ax, line1, line2)
```

<pre data-manim-binder data-manim-classname="PerpLineExample">
class PerpLineExample(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(PI / 3, -PI / 4)
        ax = ThreeDAxes((-5, 5), (-5, 5), (-5, 5), 10, 10, 10)
        line1 = Line3D(RIGHT \* 2, UP + OUT, color=RED)
        line2 = Line3D.perpendicular_to(line1, color=BLUE)
        self.add(ax, line1, line2)

</pre></div>

#### pointify(mob_or_point, direction=None)

Gets a point representing the center of the [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject).

* **Parameters:**
  * **mob_or_point** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) *|* [*Point3DLike*](manim.typing.md#manim.typing.Point3DLike)) – [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) or point whose center should be returned.
  * **direction** ([*Vector3D*](manim.typing.md#manim.typing.Vector3D)) – If an edge of a [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) should be returned, the direction of the edge.
* **Returns:**
  Center of the [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) or point, or edge if direction is given.
* **Return type:**
  `numpy.array`

#### set_start_and_end_attrs(start, end, \*\*kwargs)

Sets the start and end points of the line.

If either `start` or `end` are [`Mobjects`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject),
this gives their centers.

* **Parameters:**
  * **start** (*ndarray*) – Starting point or `Mobject`.
  * **end** (*ndarray*) – Ending point or `Mobject`.
* **Return type:**
  None

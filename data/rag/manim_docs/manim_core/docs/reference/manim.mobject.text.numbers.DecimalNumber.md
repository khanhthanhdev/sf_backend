# DecimalNumber

Qualified name: `manim.mobject.text.numbers.DecimalNumber`

### *class* DecimalNumber(number=0, num_decimal_places=2, mob_class=<class 'manim.mobject.text.tex_mobject.MathTex'>, include_sign=False, group_with_commas=True, digit_buff_per_font_unit=0.001, show_ellipsis=False, unit=None, unit_buff_per_font_unit=0, include_background_rectangle=False, edge_to_fix=array([-1., 0., 0.]), font_size=48, stroke_width=0, fill_opacity=1.0, \*\*kwargs)

Bases: [`VMobject`](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject)

An mobject representing a decimal number.

* **Parameters:**
  * **number** (*float*) – The numeric value to be displayed. It can later be modified using [`set_value()`](#manim.mobject.text.numbers.DecimalNumber.set_value).
  * **num_decimal_places** (*int*) – The number of decimal places after the decimal separator. Values are automatically rounded.
  * **mob_class** ([*VMobject*](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject)) – The class for rendering digits and units, by default [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex).
  * **include_sign** (*bool*) – Set to `True` to include a sign for positive numbers and zero.
  * **group_with_commas** (*bool*) – When `True` thousands groups are separated by commas for readability.
  * **digit_buff_per_font_unit** (*float*) – Additional spacing between digits. Scales with font size.
  * **show_ellipsis** (*bool*) – When a number has been truncated by rounding, indicate with an ellipsis (`...`).
  * **unit** (*str* *|* *None*) – A unit string which can be placed to the right of the numerical values.
  * **unit_buff_per_font_unit** (*float*) – An additional spacing between the numerical values and the unit. A value
    of `unit_buff_per_font_unit=0.003` gives a decent spacing. Scales with font size.
  * **include_background_rectangle** (*bool*) – Adds a background rectangle to increase contrast on busy scenes.
  * **edge_to_fix** (*Sequence* *[**float* *]*) – Assuring right- or left-alignment of the full object.
  * **font_size** (*float*) – Size of the font.
  * **stroke_width** (*float*)
  * **fill_opacity** (*float*)

### Examples

<div id="movingsquarewithupdaters" class="admonition admonition-manim-example">
<p class="admonition-title">Example: MovingSquareWithUpdaters <a class="headerlink" href="#movingsquarewithupdaters">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./MovingSquareWithUpdaters-1.mp4">
</video>
```python
from manim import *

class MovingSquareWithUpdaters(Scene):
    def construct(self):
        decimal = DecimalNumber(
            0,
            show_ellipsis=True,
            num_decimal_places=3,
            include_sign=True,
            unit=r"\text{M-Units}",
            unit_buff_per_font_unit=0.003
        )
        square = Square().to_edge(UP)

        decimal.add_updater(lambda d: d.next_to(square, RIGHT))
        decimal.add_updater(lambda d: d.set_value(square.get_center()[1]))
        self.add(square, decimal)
        self.play(
            square.animate.to_edge(DOWN),
            rate_func=there_and_back,
            run_time=5,
        )
        self.wait()
```

<pre data-manim-binder data-manim-classname="MovingSquareWithUpdaters">
class MovingSquareWithUpdaters(Scene):
    def construct(self):
        decimal = DecimalNumber(
            0,
            show_ellipsis=True,
            num_decimal_places=3,
            include_sign=True,
            unit=r"\\text{M-Units}",
            unit_buff_per_font_unit=0.003
        )
        square = Square().to_edge(UP)

        decimal.add_updater(lambda d: d.next_to(square, RIGHT))
        decimal.add_updater(lambda d: d.set_value(square.get_center()[1]))
        self.add(square, decimal)
        self.play(
            square.animate.to_edge(DOWN),
            rate_func=there_and_back,
            run_time=5,
        )
        self.wait()

</pre></div>

### Methods

| `get_value`                                                        |                                                                                                    |
|--------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| `increment_value`                                                  |                                                                                                    |
| [`set_value`](#manim.mobject.text.numbers.DecimalNumber.set_value) | Set the value of the [`DecimalNumber`](#manim.mobject.text.numbers.DecimalNumber) to a new number. |

### Attributes

| `animate`                                                          | Used to animate the application of any method of `self`.               |
|--------------------------------------------------------------------|------------------------------------------------------------------------|
| `animation_overrides`                                              |                                                                        |
| `color`                                                            |                                                                        |
| `depth`                                                            | The depth of the mobject.                                              |
| `fill_color`                                                       | If there are multiple colors (for gradient) this returns the first one |
| [`font_size`](#manim.mobject.text.numbers.DecimalNumber.font_size) | The font size of the tex mobject.                                      |
| `height`                                                           | The height of the mobject.                                             |
| `n_points_per_curve`                                               |                                                                        |
| `sheen_factor`                                                     |                                                                        |
| `stroke_color`                                                     |                                                                        |
| `width`                                                            | The width of the mobject.                                              |

#### \_get_formatter(\*\*kwargs)

Configuration is based first off instance attributes,
but overwritten by any kew word argument.  Relevant
key words:
- include_sign
- group_with_commas
- num_decimal_places
- field_name (e.g. 0 or 0.real)

#### \_original_\_init_\_(number=0, num_decimal_places=2, mob_class=<class 'manim.mobject.text.tex_mobject.MathTex'>, include_sign=False, group_with_commas=True, digit_buff_per_font_unit=0.001, show_ellipsis=False, unit=None, unit_buff_per_font_unit=0, include_background_rectangle=False, edge_to_fix=array([-1., 0., 0.]), font_size=48, stroke_width=0, fill_opacity=1.0, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **number** (*float*)
  * **num_decimal_places** (*int*)
  * **mob_class** ([*VMobject*](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject))
  * **include_sign** (*bool*)
  * **group_with_commas** (*bool*)
  * **digit_buff_per_font_unit** (*float*)
  * **show_ellipsis** (*bool*)
  * **unit** (*str* *|* *None*)
  * **unit_buff_per_font_unit** (*float*)
  * **include_background_rectangle** (*bool*)
  * **edge_to_fix** (*Sequence* *[**float* *]*)
  * **font_size** (*float*)
  * **stroke_width** (*float*)
  * **fill_opacity** (*float*)

#### *property* font_size

The font size of the tex mobject.

#### set_value(number)

Set the value of the [`DecimalNumber`](#manim.mobject.text.numbers.DecimalNumber) to a new number.

* **Parameters:**
  **number** (*float*) – The value that will overwrite the current number of the [`DecimalNumber`](#manim.mobject.text.numbers.DecimalNumber).

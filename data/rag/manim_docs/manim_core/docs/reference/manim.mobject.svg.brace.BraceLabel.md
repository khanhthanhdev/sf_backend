# BraceLabel

Qualified name: `manim.mobject.svg.brace.BraceLabel`

### *class* BraceLabel(obj, text, brace_direction=array([ 0., -1., 0.]), label_constructor=<class 'manim.mobject.text.tex_mobject.MathTex'>, font_size=48, buff=0.2, brace_config=None, \*\*kwargs)

Bases: [`VMobject`](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject)

Create a brace with a label attached.

* **Parameters:**
  * **obj** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The mobject adjacent to which the brace is placed.
  * **text** (*str*) – The label text.
  * **brace_direction** (*np.ndarray*) – The direction of the brace. By default `DOWN`.
  * **label_constructor** (*type*) – A class or function used to construct a mobject representing
    the label. By default [`MathTex`](manim.mobject.text.tex_mobject.MathTex.md#manim.mobject.text.tex_mobject.MathTex).
  * **font_size** (*float*) – The font size of the label, passed to the `label_constructor`.
  * **buff** (*float*) – The buffer between the mobject and the brace.
  * **brace_config** (*dict* *|* *None*) – Arguments to be passed to [`Brace`](manim.mobject.svg.brace.Brace.md#manim.mobject.svg.brace.Brace).
  * **kwargs** – Additional arguments to be passed to [`VMobject`](manim.mobject.types.vectorized_mobject.VMobject.md#manim.mobject.types.vectorized_mobject.VMobject).

### Methods

| `change_brace_label`   |    |
|------------------------|----|
| `change_label`         |    |
| `creation_anim`        |    |
| `shift_brace`          |    |

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

#### \_original_\_init_\_(obj, text, brace_direction=array([ 0., -1., 0.]), label_constructor=<class 'manim.mobject.text.tex_mobject.MathTex'>, font_size=48, buff=0.2, brace_config=None, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **obj** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject))
  * **text** (*str*)
  * **brace_direction** (*ndarray*)
  * **label_constructor** (*type*)
  * **font_size** (*float*)
  * **buff** (*float*)
  * **brace_config** (*dict* *|* *None*)

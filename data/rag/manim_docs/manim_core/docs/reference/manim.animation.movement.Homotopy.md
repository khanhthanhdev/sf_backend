# Homotopy

Qualified name: `manim.animation.movement.Homotopy`

### *class* Homotopy(mobject=None, \*args, use_override=True, \*\*kwargs)

Bases: [`Animation`](manim.animation.animation.Animation.md#manim.animation.animation.Animation)

A Homotopy.

This is an animation transforming the points of a mobject according
to the specified transformation function. With the parameter $t$
moving from 0 to 1 throughout the animation and $(x, y, z)$
describing the coordinates of the point of a mobject,
the function passed to the `homotopy` keyword argument should
transform the tuple $(x, y, z, t)$ to $(x', y', z')$,
the coordinates the original point is transformed to at time $t$.

* **Parameters:**
  * **homotopy** (*Callable* *[* *[**float* *,* *float* *,* *float* *,* *float* *]* *,* *tuple* *[**float* *,* *float* *,* *float* *]* *]*) – A function mapping $(x, y, z, t)$ to $(x', y', z')$.
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The mobject transformed under the given homotopy.
  * **run_time** (*float*) – The run time of the animation.
  * **apply_function_kwargs** (*dict* *[**str* *,* *Any* *]*  *|* *None*) – Keyword arguments propagated to `Mobject.apply_function()`.
  * **kwargs** – Further keyword arguments passed to the parent class.

### Examples

<div id="homotopyexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: HomotopyExample <a class="headerlink" href="#homotopyexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./HomotopyExample-1.mp4">
</video>
```python
from manim import *

class HomotopyExample(Scene):
    def construct(self):
        square = Square()

        def homotopy(x, y, z, t):
            if t <= 0.25:
                progress = t / 0.25
                return (x, y + progress * 0.2 * np.sin(x), z)
            else:
                wave_progress = (t - 0.25) / 0.75
                return (x, y + 0.2 * np.sin(x + 10 * wave_progress), z)

        self.play(Homotopy(homotopy, square, rate_func= linear, run_time=2))
```

<pre data-manim-binder data-manim-classname="HomotopyExample">
class HomotopyExample(Scene):
    def construct(self):
        square = Square()

        def homotopy(x, y, z, t):
            if t <= 0.25:
                progress = t / 0.25
                return (x, y + progress \* 0.2 \* np.sin(x), z)
            else:
                wave_progress = (t - 0.25) / 0.75
                return (x, y + 0.2 \* np.sin(x + 10 \* wave_progress), z)

        self.play(Homotopy(homotopy, square, rate_func= linear, run_time=2))

</pre></div>

### Methods

| `function_at_time_t`     |    |
|--------------------------|----|
| `interpolate_submobject` |    |

### Attributes

| `run_time`   |    |
|--------------|----|

#### \_original_\_init_\_(homotopy, mobject, run_time=3, apply_function_kwargs=None, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **homotopy** (*Callable* *[* *[**float* *,* *float* *,* *float* *,* *float* *]* *,* *tuple* *[**float* *,* *float* *,* *float* *]* *]*)
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject))
  * **run_time** (*float*)
  * **apply_function_kwargs** (*dict* *[**str* *,* *Any* *]*  *|* *None*)
* **Return type:**
  None

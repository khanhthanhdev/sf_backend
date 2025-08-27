# ChangeSpeed

Qualified name: `manim.animation.speedmodifier.ChangeSpeed`

### *class* ChangeSpeed(mobject=None, \*args, use_override=True, \*\*kwargs)

Bases: [`Animation`](manim.animation.animation.Animation.md#manim.animation.animation.Animation)

Modifies the speed of passed animation.
`AnimationGroup` with different `lag_ratio` can also be used
which combines multiple animations into one.
The `run_time` of the passed animation is changed to modify the speed.

* **Parameters:**
  * **anim** ([*Animation*](manim.animation.animation.Animation.md#manim.animation.animation.Animation) *|*  *\_AnimationBuilder*) – Animation of which the speed is to be modified.
  * **speedinfo** (*dict* *[**float* *,* *float* *]*) – Contains nodes (percentage of `run_time`) and its corresponding speed factor.
  * **rate_func** (*Callable* *[* *[**float* *]* *,* *float* *]*  *|* *None*) – Overrides `rate_func` of passed animation, applied before changing speed.
  * **affects_speed_updaters** (*bool*)

### Examples

<div id="speedmodifierexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: SpeedModifierExample <a class="headerlink" href="#speedmodifierexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./SpeedModifierExample-1.mp4">
</video>
```python
from manim import *

class SpeedModifierExample(Scene):
    def construct(self):
        a = Dot().shift(LEFT * 4)
        b = Dot().shift(RIGHT * 4)
        self.add(a, b)
        self.play(
            ChangeSpeed(
                AnimationGroup(
                    a.animate(run_time=1).shift(RIGHT * 8),
                    b.animate(run_time=1).shift(LEFT * 8),
                ),
                speedinfo={0.3: 1, 0.4: 0.1, 0.6: 0.1, 1: 1},
                rate_func=linear,
            )
        )
```

<pre data-manim-binder data-manim-classname="SpeedModifierExample">
class SpeedModifierExample(Scene):
    def construct(self):
        a = Dot().shift(LEFT \* 4)
        b = Dot().shift(RIGHT \* 4)
        self.add(a, b)
        self.play(
            ChangeSpeed(
                AnimationGroup(
                    a.animate(run_time=1).shift(RIGHT \* 8),
                    b.animate(run_time=1).shift(LEFT \* 8),
                ),
                speedinfo={0.3: 1, 0.4: 0.1, 0.6: 0.1, 1: 1},
                rate_func=linear,
            )
        )

</pre></div><div id="speedmodifierupdaterexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: SpeedModifierUpdaterExample <a class="headerlink" href="#speedmodifierupdaterexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./SpeedModifierUpdaterExample-1.mp4">
</video>
```python
from manim import *

class SpeedModifierUpdaterExample(Scene):
    def construct(self):
        a = Dot().shift(LEFT * 4)
        self.add(a)

        ChangeSpeed.add_updater(a, lambda x, dt: x.shift(RIGHT * 4 * dt))
        self.play(
            ChangeSpeed(
                Wait(2),
                speedinfo={0.4: 1, 0.5: 0.2, 0.8: 0.2, 1: 1},
                affects_speed_updaters=True,
            )
        )
```

<pre data-manim-binder data-manim-classname="SpeedModifierUpdaterExample">
class SpeedModifierUpdaterExample(Scene):
    def construct(self):
        a = Dot().shift(LEFT \* 4)
        self.add(a)

        ChangeSpeed.add_updater(a, lambda x, dt: x.shift(RIGHT \* 4 \* dt))
        self.play(
            ChangeSpeed(
                Wait(2),
                speedinfo={0.4: 1, 0.5: 0.2, 0.8: 0.2, 1: 1},
                affects_speed_updaters=True,
            )
        )

</pre></div><div id="speedmodifierupdaterexample2" class="admonition admonition-manim-example">
<p class="admonition-title">Example: SpeedModifierUpdaterExample2 <a class="headerlink" href="#speedmodifierupdaterexample2">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./SpeedModifierUpdaterExample2-1.mp4">
</video>
```python
from manim import *

class SpeedModifierUpdaterExample2(Scene):
    def construct(self):
        a = Dot().shift(LEFT * 4)
        self.add(a)

        ChangeSpeed.add_updater(a, lambda x, dt: x.shift(RIGHT * 4 * dt))
        self.wait()
        self.play(
            ChangeSpeed(
                Wait(),
                speedinfo={1: 0},
                affects_speed_updaters=True,
            )
        )
```

<pre data-manim-binder data-manim-classname="SpeedModifierUpdaterExample2">
class SpeedModifierUpdaterExample2(Scene):
    def construct(self):
        a = Dot().shift(LEFT \* 4)
        self.add(a)

        ChangeSpeed.add_updater(a, lambda x, dt: x.shift(RIGHT \* 4 \* dt))
        self.wait()
        self.play(
            ChangeSpeed(
                Wait(),
                speedinfo={1: 0},
                affects_speed_updaters=True,
            )
        )

</pre></div>

### Methods

| [`add_updater`](#manim.animation.speedmodifier.ChangeSpeed.add_updater)                     | This static method can be used to apply speed change to updaters.                                         |
|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| [`begin`](#manim.animation.speedmodifier.ChangeSpeed.begin)                                 | Begin the animation.                                                                                      |
| [`clean_up_from_scene`](#manim.animation.speedmodifier.ChangeSpeed.clean_up_from_scene)     | Clean up the [`Scene`](manim.scene.scene.Scene.md#manim.scene.scene.Scene) after finishing the animation. |
| [`finish`](#manim.animation.speedmodifier.ChangeSpeed.finish)                               | Finish the animation.                                                                                     |
| [`get_scaled_total_time`](#manim.animation.speedmodifier.ChangeSpeed.get_scaled_total_time) | The time taken by the animation under the assumption that the `run_time` is 1.                            |
| [`interpolate`](#manim.animation.speedmodifier.ChangeSpeed.interpolate)                     | Set the animation progress.                                                                               |
| `setup`                                                                                     |                                                                                                           |
| [`update_mobjects`](#manim.animation.speedmodifier.ChangeSpeed.update_mobjects)             | Updates things like starting_mobject, and (for Transforms) target_mobject.                                |

### Attributes

| `dt`             |    |
|------------------|----|
| `is_changing_dt` |    |
| `run_time`       |    |

#### \_original_\_init_\_(anim, speedinfo, rate_func=None, affects_speed_updaters=True, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **anim** ([*Animation*](manim.animation.animation.Animation.md#manim.animation.animation.Animation) *|*  *\_AnimationBuilder*)
  * **speedinfo** (*dict* *[**float* *,* *float* *]*)
  * **rate_func** (*Callable* *[* *[**float* *]* *,* *float* *]*  *|* *None*)
  * **affects_speed_updaters** (*bool*)
* **Return type:**
  None

#### \_setup_scene(scene)

Setup up the [`Scene`](manim.scene.scene.Scene.md#manim.scene.scene.Scene) before starting the animation.

This includes to [`add()`](manim.scene.scene.Scene.md#manim.scene.scene.Scene.add) the Animation’s
[`Mobject`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) if the animation is an introducer.

* **Parameters:**
  **scene** – The scene the animation should be cleaned up from.
* **Return type:**
  None

#### *classmethod* add_updater(mobject, update_function, index=None, call_updater=False)

This static method can be used to apply speed change to updaters.

This updater will follow speed and rate function of any [`ChangeSpeed`](#manim.animation.speedmodifier.ChangeSpeed)
animation that is playing with `affects_speed_updaters=True`. By default,
updater functions added via the usual [`Mobject.add_updater()`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject.add_updater) method
do not respect the change of animation speed.

* **Parameters:**
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The mobject to which the updater should be attached.
  * **update_function** (*Updater*) – The function that is called whenever a new frame is rendered.
  * **index** (*int* *|* *None*) – The position in the list of the mobject’s updaters at which the
    function should be inserted.
  * **call_updater** (*bool*) – If `True`, calls the update function when attaching it to the
    mobject.

#### SEE ALSO
[`ChangeSpeed`](#manim.animation.speedmodifier.ChangeSpeed), [`Mobject.add_updater()`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject.add_updater)

#### begin()

Begin the animation.

This method is called right as an animation is being played. As much
initialization as possible, especially any mobject copying, should live in this
method.

* **Return type:**
  None

#### clean_up_from_scene(scene)

Clean up the [`Scene`](manim.scene.scene.Scene.md#manim.scene.scene.Scene) after finishing the animation.

This includes to [`remove()`](manim.scene.scene.Scene.md#manim.scene.scene.Scene.remove) the Animation’s
[`Mobject`](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject) if the animation is a remover.

* **Parameters:**
  **scene** ([*Scene*](manim.scene.scene.Scene.md#manim.scene.scene.Scene)) – The scene the animation should be cleaned up from.
* **Return type:**
  None

#### finish()

Finish the animation.

This method gets called when the animation is over.

* **Return type:**
  None

#### get_scaled_total_time()

The time taken by the animation under the assumption that the `run_time` is 1.

* **Return type:**
  float

#### interpolate(alpha)

Set the animation progress.

This method gets called for every frame during an animation.

* **Parameters:**
  **alpha** (*float*) – The relative time to set the animation to, 0 meaning the start, 1 meaning
  the end.
* **Return type:**
  None

#### update_mobjects(dt)

Updates things like starting_mobject, and (for
Transforms) target_mobject.  Note, since typically
(always?) self.mobject will have its updating
suspended during the animation, this will do
nothing to self.mobject.

* **Parameters:**
  **dt** (*float*)
* **Return type:**
  None

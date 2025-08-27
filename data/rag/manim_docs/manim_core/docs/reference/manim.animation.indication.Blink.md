# Blink

Qualified name: `manim.animation.indication.Blink`

### *class* Blink(mobject=None, \*args, use_override=True, \*\*kwargs)

Bases: [`Succession`](manim.animation.composition.Succession.md#manim.animation.composition.Succession)

Blink the mobject.

* **Parameters:**
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject)) – The mobject to be blinked.
  * **time_on** (*float*) – The duration that the mobject is shown for one blink.
  * **time_off** (*float*) – The duration that the mobject is hidden for one blink.
  * **blinks** (*int*) – The number of blinks
  * **hide_at_end** (*bool*) – Whether to hide the mobject at the end of the animation.
  * **kwargs** – Additional arguments to be passed to the [`Succession`](manim.animation.composition.Succession.md#manim.animation.composition.Succession) constructor.

### Examples

<div id="blinkingexample" class="admonition admonition-manim-example">
<p class="admonition-title">Example: BlinkingExample <a class="headerlink" href="#blinkingexample">¶</a></p><video
    class="manim-video"
    controls
    loop
    autoplay
    src="./BlinkingExample-1.mp4">
</video>
```python
from manim import *

class BlinkingExample(Scene):
    def construct(self):
        text = Text("Blinking").scale(1.5)
        self.add(text)
        self.play(Blink(text, blinks=3))
```

<pre data-manim-binder data-manim-classname="BlinkingExample">
class BlinkingExample(Scene):
    def construct(self):
        text = Text("Blinking").scale(1.5)
        self.add(text)
        self.play(Blink(text, blinks=3))

</pre></div>

### Methods

### Attributes

| `run_time`   |    |
|--------------|----|

#### \_original_\_init_\_(mobject, time_on=0.5, time_off=0.5, blinks=1, hide_at_end=False, \*\*kwargs)

Initialize self.  See help(type(self)) for accurate signature.

* **Parameters:**
  * **mobject** ([*Mobject*](manim.mobject.mobject.Mobject.md#manim.mobject.mobject.Mobject))
  * **time_on** (*float*)
  * **time_off** (*float*)
  * **blinks** (*int*)
  * **hide_at_end** (*bool*)

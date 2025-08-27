# Visualizing Neural Networks with ManimML

This is a tutorial on how to make neural network architecture visualizations
and animate common algorithms like the forward pass of a neural network.
Neural networks are a ubiquitous class of machine learning techniques.
One of the primary usecases for ManimML is for generating animations of neural network architectures.
We have attempted to construct a simple API for defining neural network architectures
that should feel native to anyone who has used popular deep learning libraries like Pytorch, Tensorflow, and Keras.
User’s can define a sequence of layers and we prove a system for automatically generating various
animations of concepts like a forward pass. We also allow the user to change the style of rendered
architectures and algorithm animations.

For this tutorial we assume that you have already followed the [Getting Started](getting_started.md) tutorial.
This tutorial goes over several simple topics:

1. Generating a simple feed forward neural network diagram
2. Animating the forward pass of a feed forward neural network
3. Generating a diagram of a convolutional neural network
4. Modifying the default style of a neural network

The topics of other tutorials will include:

1. Creating custom neural network layers
2. Creating custom animations of neural networks

## Visualizing a Feed Forward Neural Network Test

<div id="feedforwardnetworkscene" class="admonition admonition-manim-example">
<p class="admonition-title">Example: FeedForwardNetworkScene <a class="headerlink" href="#feedforwardnetworkscene">¶</a></p>![image](media/images/FeedForwardNetworkScene-1.png)
```python
from manim import *

class FeedForwardNetworkScene(Scene):

    def construct(self):
        from manim_ml.neural_network import NeuralNetwork
        from manim_ml.neural_network.layers import FeedForwardLayer

        neural_network = NeuralNetwork([
            FeedForwardLayer(3),
            FeedForwardLayer(5),
            FeedForwardLayer(2),
            FeedForwardLayer(4)
        ])
        self.add(neural_network)
```

<pre data-manim-binder data-manim-classname="FeedForwardNetworkScene">
class FeedForwardNetworkScene(Scene):

    def construct(self):
        from manim_ml.neural_network import NeuralNetwork
        from manim_ml.neural_network.layers import FeedForwardLayer

        neural_network = NeuralNetwork([
            FeedForwardLayer(3),
            FeedForwardLayer(5),
            FeedForwardLayer(2),
            FeedForwardLayer(4)
        ])
        self.add(neural_network)

</pre></div>

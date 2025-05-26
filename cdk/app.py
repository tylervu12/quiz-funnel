#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk.quiz_funnel_stack import QuizFunnelStack

app = cdk.App()
QuizFunnelStack(app, "quiz-funnel-stack")  # this is the name in AWS Console
app.synth()
class DeploymentPodMapping:
    """ Point class represents and manipulates x,y coords. """

    def __init__(self, deployment):
        """ Create a new point at the origin """
        self.deployment = deployment
        self.pods = []

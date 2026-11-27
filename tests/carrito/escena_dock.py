import math

from geometria_dock.transformaciones import Pose2D


def _prod(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def tag_visto(robot, camara, tag, inclinacion=0.0, h_camara=0.12, h_tag=0.12):
    """Pose del tag que mediría la cámara: escena física en 3D, independiente de carrito.marcos.
    robot, camara, tag: Pose2D en el dock / en el robot / en el dock. Devuelve x, y, z (m) y dth (grados) y la matriz R."""
    psi = robot.th + camara.th
    c, s = math.cos(robot.th), math.sin(robot.th)
    p_cam = (robot.x + c * camara.x - s * camara.y, robot.y + s * camara.x + c * camara.y, h_camara)
    f = (math.cos(psi) * math.cos(inclinacion), math.sin(psi) * math.cos(inclinacion), -math.sin(inclinacion))
    r = (math.sin(psi), -math.cos(psi), 0.0)
    d = _prod(f, r)
    ejes_cam = (r, d, f)
    zt = (math.cos(tag.th), math.sin(tag.th), 0.0)
    yt = (0.0, 0.0, -1.0)
    xt = _prod(yt, zt)
    ejes_tag = (xt, yt, zt)
    dot = lambda a, b: sum(u * v for u, v in zip(a, b))
    R = [[dot(ejes_cam[i], ejes_tag[j]) for j in range(3)] for i in range(3)]
    delta = (tag.x - p_cam[0], tag.y - p_cam[1], h_tag - p_cam[2])
    t = tuple(dot(ejes_cam[i], delta) for i in range(3))
    dth = math.degrees(math.atan2(R[0][2], R[2][2]))
    return t[0], t[1], t[2], dth, R

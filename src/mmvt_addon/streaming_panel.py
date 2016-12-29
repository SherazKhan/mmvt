import bpy
import mmvt_utils as mu
import sys
import os.path as op
import time
import numpy as np
import traceback
from itertools import cycle
from datetime import datetime


def _addon():
    return StreamingPanel.addon


# @mu.timeit
def change_graph_all_vals(mat, condition = 'interference'):
    print(str(datetime.now() - StreamingPanel.time))
    StreamingPanel.time = datetime.now()
    T = min(mat.shape[1], _addon().get_max_time_steps())
    for elc_ind, elc_name in enumerate(StreamingPanel.electrodes_names):
        bpy.data.objects[elc_name].select = True
        parent_obj = bpy.data.objects[elc_name]
        curve_name = '{}_{}'.format(elc_name, condition)
        for fcurve in parent_obj.animation_data.action.fcurves:
            if mu.get_fcurve_name(fcurve) != curve_name:
                fcurve.hide = True
                continue
            fcurve.hide = False
            N = len(fcurve.keyframe_points)
            for ind in range(N - 1, T - 1, -1):
                fcurve.keyframe_points[ind].co[1] = fcurve.keyframe_points[ind - T].co[1]
            for ind in range(T):
                fcurve.keyframe_points[ind].co[1] = mat[elc_ind][ind]
            fcurve.keyframe_points[N - 1].co[1] = 0
            fcurve.keyframe_points[0].co[1] = 0


def change_color(obj, val, data_min, colors_ratio):
    colors_ind = calc_color_ind(val, data_min, colors_ratio)
    colors = StreamingPanel.cm[colors_ind]
    _addon().object_coloring(obj, colors)


def calc_color_ind(val, data_min, colors_ratio):
    colors_ind = int(((val - data_min) * colors_ratio))
    N = len(StreamingPanel.cm)
    if colors_ind < 0:
        colors_ind = 0
    if colors_ind > N - 1:
        colors_ind = N - 1
    return colors_ind


def reading_from_udp_while_termination_func():
    return StreamingPanel.is_streaming


def udp_reader(udp_ts_queue, udp_viz_queue, while_termination_func, **kargs):
    import socket
    buffer_size = kargs.get('buffer_size', 10)
    server = kargs.get('server', 'localhost')
    ip = kargs.get('ip', 10000)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (server, ip)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(server_address)
    buffer = []

    while while_termination_func():
        next_val = sock.recv(4096)
        next_val = next_val.decode(sys.getfilesystemencoding(), 'ignore')
        next_val = np.array([float(f) for f in next_val.split(',')])
        next_val = next_val[..., np.newaxis]
        udp_viz_queue.put(buffer)
        buffer = next_val if buffer == [] else np.hstack((buffer, next_val))
        if buffer.shape[1] >= buffer_size:
            udp_ts_queue.put(buffer)
            buffer = []


class StreamButton(bpy.types.Operator):
    bl_idname = "mmvt.stream_button"
    bl_label = "Stream botton"
    bl_options = {"UNDO"}

    _timer = None
    _time = time.time()
    _index = 0
    _obj = None
    _buffer = []

    def invoke(self, context, event=None):
        StreamingPanel.is_streaming = not StreamingPanel.is_streaming
        if StreamingPanel.first_time:
            StreamingPanel.first_time = False
            try:
                context.window_manager.event_timer_remove(self._timer)
            except:
                pass
            context.window_manager.modal_handler_add(self)
            self._timer = context.window_manager.event_timer_add(0.01, context.window)
        if StreamingPanel.is_streaming:
            args = dict(buffer_size=500, server='localhost', ip=10000)
            StreamingPanel.udp_ts_queue, StreamingPanel.udp_viz_queue = \
                mu.run_thread_2q(udp_reader, reading_from_udp_while_termination_func, **args)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            StreamingPanel.is_streaming = False
            bpy.context.scene.update()
            self.cancel(context)
            return {'PASS_THROUGH'}

        if event.type == 'TIMER':
            # if time.time() - self._time >= 0.5:
            #     self._time = time.time()
            if not StreamingPanel.is_streaming:
                if self._buffer == [] or self._buffer.shape[1] < _addon().get_max_time_steps():
                    data = np.zeros(
                        (len(StreamingPanel.electrodes_names), bpy.context.scene.straming_buffer_size))
                    self._buffer = data if self._buffer == [] else np.hstack((self._buffer, data))
            else:
                data = mu.queue_get(StreamingPanel.udp_ts_queue)
                if not data is None:
                    self._buffer = data if self._buffer == [] else np.hstack((self._buffer, data))
                    print(str(datetime.now() - StreamingPanel.time))
                    StreamingPanel.time = datetime.now()
                    if self._buffer.shape[1] >= bpy.context.scene.straming_buffer_size:
                        # change_graph_all_vals(self._buffer)
                        self._buffer = []

                data = mu.queue_get(StreamingPanel.udp_viz_queue)
                if not data is None:
                    _addon().color_objects_homogeneously(
                        data, StreamingPanel.electrodes_names, StreamingPanel.electrodes_conditions,
                        StreamingPanel.data_min, StreamingPanel.electrodes_colors_ratio, threshold=0)

        return {'PASS_THROUGH'}

    def cancel(self, context):
        try:
            context.window_manager.event_timer_remove(self._timer)
        except:
            pass
        self._timer = None
        return {'CANCELLED'}


def template_draw(self, context):
    layout = self.layout
    layout.prop(context.scene, "straming_buffer_size", text="buffer size:")
    # layout.operator(StreamListenerButton.bl_idname,
    #                 text="Start Listener" if not StreamingPanel.is_listening else 'Stop Listener',
    #                 icon='COLOR_GREEN' if not StreamingPanel.is_listening else 'COLOR_RED')
    layout.operator(StreamButton.bl_idname,
                    text="Stream data" if not StreamingPanel.is_streaming else 'Stop streaming data',
                    icon='COLOR_GREEN' if not StreamingPanel.is_streaming else 'COLOR_RED')


bpy.types.Scene.straming_buffer_size = bpy.props.IntProperty(default=100, min=10)


class StreamingPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Stream"
    addon = None
    init = False
    is_streaming = False
    is_listening = False
    first_time = True
    # fixed_data = []
    udp_ts_queue = None
    udp_viz_queue = None
    electrodes_file = None
    time = datetime.now()
    electrodes_names, electrodes_conditions = [], []
    data_max, data_min, electrodes_colors_ratio = 0, 0, 1

    def draw(self, context):
        if StreamingPanel.init:
            template_draw(self, context)


def init(addon):
    cm_fname = op.join(mu.file_fol(), 'color_maps', 'BuPu_YlOrRd.npy')
    if not op.isfile(cm_fname):
        return
    StreamingPanel.addon = addon
    StreamingPanel.is_listening = False
    StreamingPanel.is_streaming = False
    StreamingPanel.first_time = True
    register()
    StreamingPanel.cm = np.load(cm_fname)
    # StreamingPanel.fixed_data = fixed_data()
    electrodes_data, StreamingPanel.electrodes_names, StreamingPanel.electrodes_conditions = \
        _addon().load_electrodes_data()
    norm_percs = (3, 97) #todo: add to gui
    StreamingPanel.data_max, StreamingPanel.data_min = mu.get_data_max_min(
        electrodes_data, True, norm_percs=norm_percs, data_per_hemi=False, symmetric=True)
    StreamingPanel.electrodes_colors_ratio = 256 / (StreamingPanel.data_max - StreamingPanel.data_min)

    StreamingPanel.init = True


def register():
    try:
        unregister()
        bpy.utils.register_class(StreamingPanel)
        bpy.utils.register_class(StreamButton)
        # bpy.utils.register_class(StreamListenerButton)
    except:
        print("Can't register Stream Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(StreamingPanel)
        bpy.utils.unregister_class(StreamButton)
        # bpy.utils.unregister_class(StreamListenerButton)
    except:
        pass
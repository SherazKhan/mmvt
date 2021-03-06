import bpy
import mmvt_utils as mu
import colors_utils as cu
import numpy as np
import os.path as op
import time
import itertools
from collections import defaultdict, OrderedDict
import glob
import traceback
from functools import partial

HEMIS = mu.HEMIS
(WIC_MEG, WIC_MEG_LABELS, WIC_FMRI, WIC_FMRI_CLUSTERS, WIC_ELECTRODES, WIC_ELECTRODES_SOURCES, WIC_ELECTRODES_STIM,
    WIC_MANUALLY, WIC_GROUPS, WIC_VOLUMES) = range(10)


def _addon():
    return ColoringMakerPanel.addon


def set_threshold(val):
    bpy.context.scene.coloring_threshold = val


def can_color_obj(obj):
    cur_mat = obj.active_material
    return 'RGB' in cur_mat.node_tree.nodes


def object_coloring(obj, rgb):
    if not obj:
        print('object_coloring: obj is None!')
        return False
    bpy.context.scene.objects.active = obj
    # todo: do we need to select the object here? In diff mode it's a problem
    # obj.select = True
    cur_mat = obj.active_material
    new_color = (rgb[0], rgb[1], rgb[2], 1)
    cur_mat.diffuse_color = new_color[:3]
    if can_color_obj(obj):
        cur_mat.node_tree.nodes["RGB"].outputs[0].default_value = new_color
    else:
        print("Can't color {}".format(obj.name))
        return False
    # new_color = get_obj_color(obj)
    # print('{} new color: {}'.format(obj.name, new_color))
    if _addon().is_solid():
        cur_mat.use_nodes = False
    else:
        cur_mat.use_nodes = True
    # print(cur_mat.diffuse_color)
    return True


def get_obj_color(obj):
    cur_mat = obj.active_material
    try:
        if can_color_obj(obj):
            cur_color = tuple(cur_mat.node_tree.nodes["RGB"].outputs[0].default_value)
        else:
            cur_color = (1, 1, 1)
    except:
        cur_color = (1, 1, 1)
        print("Can't get the color!")
    return cur_color


def clear_subcortical_fmri_activity():
    for cur_obj in bpy.data.objects['Subcortical_fmri_activity_map'].children:
        clear_object_vertex_colors(cur_obj)


def clear_cortex(hemis=HEMIS):
    for hemi in hemis:
        if bpy.context.scene.coloring_both_pial_and_inflated:
            for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
                clear_object_vertex_colors(cur_obj)
        else:
            if _addon().is_pial():
                cur_obj = bpy.data.objects[hemi]
            elif _addon().is_inflated():
                cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
            clear_object_vertex_colors(cur_obj)


#todo: call this code from the coloring
def clear_object_vertex_colors(cur_obj):
    mesh = cur_obj.data
    scn = bpy.context.scene
    scn.objects.active = cur_obj
    cur_obj.select = True
    # bpy.ops.mesh.vertex_color_remove()
    # vcol_layer = mesh.vertex_colors.new()
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        mesh.vertex_colors.active_index = 1
    if not (len(mesh.vertex_colors) == 1 and 'inflated' in cur_obj.name):
        bpy.ops.mesh.vertex_color_remove()
    vcol_layer = mesh.vertex_colors.new('Col')
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        mesh.vertex_colors.active_index = 1
        mesh.vertex_colors['Col'].active_render = True


# todo: do something with the threshold parameter
# @mu.timeit
def color_objects_homogeneously(data, names, conditions, data_min, colors_ratio, threshold=0, postfix_str=''):
    if data is None:
        print('color_objects_homogeneously: No data to color!')
        return
    if names is None:
        data, names, conditions = data['data'], data['names'], data['conditions']
    default_color = (1, 1, 1)
    cur_frame = bpy.context.scene.frame_current
    for obj_name, values in zip(names, data):
        if not isinstance(obj_name, str):
            obj_name = obj_name.astype(str)
        if values.ndim == 0:
            values = [values]
        t_ind = min(len(values) - 1, cur_frame)
        if values[t_ind].ndim == 0:
            value = values[t_ind]
        elif bpy.context.scene.selection_type == 'spec_cond':
            cond_inds = np.where(conditions == bpy.context.scene.conditions_selection)[0]
            if len(cond_inds) == 0:
                print("!!! Can't find the current condition in the data['conditions'] !!!")
                return
            else:
                cond_ind = cond_inds[0]
                object_colors = object_colors[:, cond_ind]
                value = values[t_ind, cond_ind]
        else:
            value = np.diff(values[t_ind])[0]
        # todo: there is a difference between value and real_value, what should we do?
        # real_value = mu.get_fcurve_current_frame_val('Deep_electrodes', obj_name, cur_frame)
        # new_color = object_colors[cur_frame] if abs(value) > threshold else default_color
        new_color = calc_colors([value], data_min, colors_ratio)[0]
        # todo: check if the stat should be avg or diff
        obj = bpy.data.objects.get(obj_name+postfix_str)
        # if obj and not obj.hide:
        #     print('trying to color {} with {}'.format(obj_name+postfix_str, new_color))
        ret = object_coloring(obj, new_color)
        if not ret:
            print('color_objects_homogeneously: Error in coloring the object {}!'.format(obj_name))
            # print(obj_name, value, new_color)
        # else:
        #     print('color_objects_homogeneously: {} was not loaded!'.format(obj_name))

    # print('Finished coloring!!')


def init_activity_map_coloring(map_type, subcorticals=True):
    # _addon().set_appearance_show_activity_layer(bpy.context.scene, True)
    # _addon().set_filter_view_type(bpy.context.scene, 'RENDERS')
    _addon().show_activity()
    # _addon().change_to_rendered_brain()

    if not bpy.context.scene.objects_show_hide_sub_cortical:
        if subcorticals:
            _addon().show_hide_hierarchy(map_type != 'FMRI', 'Subcortical_fmri_activity_map')
            _addon().show_hide_hierarchy(map_type != 'MEG', 'Subcortical_meg_activity_map')
        else:
            _addon().show_hide_sub_corticals(not subcorticals)
    # change_view3d()


def load_faces_verts():
    faces_verts = {}
    current_root_path = mu.get_user_fol()
    faces_verts['lh'] = np.load(op.join(current_root_path, 'faces_verts_lh.npy'))
    faces_verts['rh'] = np.load(op.join(current_root_path, 'faces_verts_rh.npy'))
    # faces_verts['cortex'] = np.load(op.join(current_root_path, 'faces_verts_cortex.npy'))
    return faces_verts


def load_meg_subcortical_activity():
    meg_sub_activity = None
    subcortical_activity_file = op.join(mu.get_user_fol(), 'subcortical_meg_activity.npz')
    if op.isfile(subcortical_activity_file) and bpy.context.scene.coloring_meg_subcorticals:
        meg_sub_activity = np.load(subcortical_activity_file)
    return meg_sub_activity


def activity_map_coloring(map_type, clusters=False, threshold=None):
    init_activity_map_coloring(map_type)
    if threshold is None:
        threshold = bpy.context.scene.coloring_threshold
    meg_sub_activity = None
    if map_type == 'MEG':
        if bpy.context.scene.coloring_meg_subcorticals:
            meg_sub_activity = load_meg_subcortical_activity()
        ColoringMakerPanel.what_is_colored.add(WIC_MEG)
        mu.remove_items_from_set(ColoringMakerPanel.what_is_colored, [WIC_FMRI, WIC_FMRI_CLUSTERS])
    elif map_type == 'FMRI':
        if not clusters:
            ColoringMakerPanel.what_is_colored.add(WIC_FMRI)
        else:
            ColoringMakerPanel.what_is_colored.add(WIC_FMRI_CLUSTERS)
        mu.remove_items_from_set(ColoringMakerPanel.what_is_colored, [WIC_MEG, WIC_MEG_LABELS])
    plot_activity(map_type, ColoringMakerPanel.faces_verts, threshold, meg_sub_activity, clusters=clusters,
                  plot_subcorticals=bpy.context.scene.coloring_meg_subcorticals)
    # setup_environment_settings()


def meg_labels_coloring(override_current_mat=True):
    ColoringMakerPanel.what_is_colored.add(WIC_MEG_LABELS)
    init_activity_map_coloring('MEG')
    threshold = bpy.context.scene.coloring_threshold
    hemispheres = [hemi for hemi in HEMIS if not bpy.data.objects[hemi].hide]
    user_fol = mu.get_user_fol()
    for hemi_ind, hemi in enumerate(hemispheres):
        labels_data = np.load(op.join(user_fol, 'meg_labels_coloring_{}.npz'.format(hemi)))
        meg_labels_coloring_hemi(labels_data, ColoringMakerPanel.faces_verts,
                                 hemi, threshold, override_current_mat)


def meg_labels_coloring_hemi(labels_data, faces_verts, hemi, threshold=0, override_current_mat=True,
                             colors_min=None, colors_max=None):
    now = time.time()
    colors_ratio = None
    labels_names = ColoringMakerPanel.labels_vertices['labels_names']
    labels_vertices = ColoringMakerPanel.labels_vertices['labels_vertices']
    vertices_num = max(itertools.chain.from_iterable(labels_vertices[hemi])) + 1
    no_t = labels_data['data'][0].ndim == 0
    t = bpy.context.scene.frame_current
    if not colors_min is None and not colors_max is None:
        colors_data = np.zeros((vertices_num))
    else:
        colors_data = np.ones((vertices_num, 4))
        colors_data[:, 0] = 0
    for label_data, label_colors, label_name in zip(labels_data['data'], labels_data['colors'], labels_data['names']):
        if label_data.ndim == 0:
            label_data = np.array([label_data])
        if not colors_min is None and not colors_max is None:
            colors_ratio = 256 / (colors_max - colors_min)
            label_colors = calc_colors(label_data, colors_min, colors_ratio)
            _addon().set_colorbar_max_min(colors_max, colors_min)
        else:
            label_colors = np.array(label_colors)
            if 'unknown' in label_name:
                continue
            if label_colors.ndim == 3:
                cond_inds = np.where(labels_data['conditions'] == bpy.context.scene.conditions_selection)[0]
                if len(cond_inds) == 0:
                    print("!!! Can't find the current condition in the data['conditions'] !!!")
                    return {"FINISHED"}
                label_colors = label_colors[:, cond_inds[0], :]
                label_data = label_data[:, cond_inds[0]]
        label_index = labels_names[hemi].index(label_name)
        label_vertices = np.array(labels_vertices[hemi][label_index])
        if len(label_vertices) > 0:
            label_data_t, label_colors_t = (label_data, label_colors) if no_t else (label_data[t], label_colors[t])
            # print('coloring {} with {}'.format(label_name, label_colors_t))
            if not colors_min is None and not colors_max is None:
                colors_data[label_vertices] = label_data_t
            else:
                label_colors_data = np.hstack((label_data_t, label_colors_t))
                label_colors_data = np.tile(label_colors_data, (len(label_vertices), 1))
                colors_data[label_vertices, :] = label_colors_data
    if bpy.context.scene.coloring_both_pial_and_inflated:
        for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
            activity_map_obj_coloring(
                cur_obj, colors_data, faces_verts[hemi], threshold, override_current_mat, colors_min, colors_ratio)
    else:
        if _addon().is_pial():
            cur_obj = bpy.data.objects[hemi]
        elif _addon().is_inflated():
            cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
        activity_map_obj_coloring(
            cur_obj, colors_data, faces_verts[hemi], threshold, override_current_mat, colors_min, colors_ratio)
    print('Finish meg_labels_coloring_hemi, hemi {}, {:.2f}s'.format(hemi, time.time()-now))


@mu.timeit
def plot_activity(map_type, faces_verts, threshold, meg_sub_activity=None,
        plot_subcorticals=True, override_current_mat=True, clusters=False):
    current_root_path = mu.get_user_fol() # bpy.path.abspath(bpy.context.scene.conf_path)
    not_hiden_hemis = [hemi for hemi in HEMIS if not bpy.data.objects[hemi].hide]
    frame_str = str(bpy.context.scene.frame_current)

    loop_indices = {}
    f = None
    for hemi in not_hiden_hemis:
        colors_ratio, data_min = None, None
        if map_type == 'MEG':
            fname = op.join(current_root_path, 'activity_map_' + hemi, 't' + frame_str + '.npy')
            if op.isfile(fname):
                f = np.load(fname)
                if _addon().colorbar_values_are_locked():
                    data_max, data_min = _addon().get_colorbar_max_min()
                    colors_ratio = 256 / (data_max - data_min)
                else:
                    colors_ratio = ColoringMakerPanel.meg_activity_colors_ratio
                    data_min = ColoringMakerPanel.meg_activity_data_min
                    data_max = ColoringMakerPanel.meg_activity_data_max
                    _addon().set_colorbar_max_min(data_max, data_min)
                _addon().set_colorbar_title('MEG')
            else:
                print("Can't load {}".format(fname))
                return False
        elif map_type == 'FMRI':
            if not ColoringMakerPanel.fmri_activity_data_min is None and \
                    not ColoringMakerPanel.fmri_activity_data_max is None:
                if _addon().colorbar_values_are_locked():
                    data_max, data_min = _addon().get_colorbar_max_min()
                    colors_ratio = 256 / (data_max - data_min)
                else:
                    colors_ratio = ColoringMakerPanel.fmri_activity_colors_ratio
                    data_min = ColoringMakerPanel.fmri_activity_data_min
                    data_max = ColoringMakerPanel.fmri_activity_data_max
                    _addon().set_colorbar_max_min(data_max, data_min)
                _addon().set_colorbar_title('fMRI')
            if clusters:
                f = [c for h, c in ColoringMakerPanel.fMRI_clusters.items() if h == hemi]
            else:
                f = ColoringMakerPanel.fMRI[hemi]
        if bpy.context.scene.coloring_both_pial_and_inflated:
            for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
                activity_map_obj_coloring(cur_obj, f, faces_verts[hemi], threshold, override_current_mat, data_min,
                                          colors_ratio)
        else:
            if _addon().is_pial():
                cur_obj = bpy.data.objects[hemi]
            elif _addon().is_inflated():
                cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
            activity_map_obj_coloring(cur_obj, f, faces_verts[hemi], threshold, override_current_mat, data_min, colors_ratio)

    if plot_subcorticals and not bpy.context.scene.objects_show_hide_sub_cortical and not meg_sub_activity is None:
        if map_type == 'MEG' and not bpy.data.objects['Subcortical_meg_activity_map'].hide:
                if f is None:
                    if _addon().colorbar_values_are_locked():
                        data_max, data_min = _addon().get_colorbar_max_min()
                        colors_ratio = 256 / (data_max - data_min)
                    else:
                        data_max, data_min = meg_sub_activity['data_minmax'], -meg_sub_activity['data_minmax']
                        colors_ratio = 256 / (2 * data_max)
                        _addon().set_colorbar_max_min(data_max, data_min)
                    _addon().set_colorbar_title('Subcortical MEG')
                color_objects_homogeneously(
                    meg_sub_activity['data'], meg_sub_activity['names'], meg_sub_activity['conditions'], data_min,
                    colors_ratio, threshold, '_meg_activity')
        elif map_type == 'FMRI' and not bpy.data.objects['Subcortical_fmri_activity_map'].hide:
            fmri_subcortex_activity_color(threshold, override_current_mat)

    return True
    # return loop_indices
    # Noam: not sure this is necessary
    #deselect_all()
    #bpy.data.objects['Brain'].select = True


def fmri_subcortex_activity_color(threshold, override_current_mat=True):
    current_root_path = mu.get_user_fol() # bpy.path.abspath(bpy.context.scene.conf_path)
    subcoticals = glob.glob(op.join(current_root_path, 'subcortical_fmri_activity', '*.npy'))
    for subcortical_file in subcoticals:
        subcortical = op.splitext(op.basename(subcortical_file))[0]
        cur_obj = bpy.data.objects.get('{}_fmri_activity'.format(subcortical))
        if cur_obj is None:
            print("Can't find the object {}!".format(subcortical))
        else:
            lookup_file = op.join(current_root_path, 'subcortical', '{}_faces_verts.npy'.format(subcortical))
            verts_file = op.join(current_root_path, 'subcortical_fmri_activity', '{}.npy'.format(subcortical))
            if op.isfile(lookup_file) and op.isfile(verts_file):
                lookup = np.load(lookup_file)
                verts_values = np.load(verts_file)
                activity_map_obj_coloring(cur_obj, verts_values, lookup, threshold, override_current_mat)


def create_inflated_curv_coloring():

    def color_obj_curvs(cur_obj, curv, lookup):
        mesh = cur_obj.data
        if not 'curve' in mesh.vertex_colors.keys():
            scn = bpy.context.scene
            verts_colors = np.zeros((curv.shape[0], 3))
            verts_colors[np.where(curv == 0)] = [1, 1, 1]
            verts_colors[np.where(curv == 1)] = [0.55, 0.55, 0.55]
            scn.objects.active = cur_obj
            cur_obj.select = True
            bpy.ops.mesh.vertex_color_remove()
            vcol_layer = mesh.vertex_colors.new('curve')
            for vert in range(curv.shape[0]):
                x = lookup[vert]
                for loop_ind in x[x>-1]:
                    d = vcol_layer.data[loop_ind]
                    d.color = verts_colors[vert]

    try:
        # todo: check not to overwrite
        print('Creating the inflated curvatures coloring')
        for hemi in mu.HEMIS:
            cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
            curv = np.load(op.join(mu.get_user_fol(), 'surf', '{}.curv.npy'.format(hemi)))
            lookup = np.load(op.join(mu.get_user_fol(), 'faces_verts_{}.npy'.format(hemi)))
            color_obj_curvs(cur_obj, curv, lookup)
        for hemi in mu.HEMIS:
            curvs_fol = op.join(mu.get_user_fol(), 'surf', '{}_{}_curves'.format(bpy.context.scene.atlas, hemi))
            lookup_fol = op.join(mu.get_user_fol(), '{}.pial.{}'.format(bpy.context.scene.atlas, hemi))
            for cur_obj in bpy.data.objects['Cortex-{}'.format(hemi)].children:
                try:
                    label = cur_obj.name
                    inflated_cur_obj = bpy.data.objects['inflated_{}'.format(label)]
                    curv = np.load(op.join(curvs_fol, '{}_curv.npy'.format(label)))
                    lookup = np.load(op.join(lookup_fol, '{}_faces_verts.npy'.format(label)))
                    color_obj_curvs(inflated_cur_obj, curv, lookup)
                except:
                    print("Can't create {}'s curves!".format(cur_obj.name))
    except:
        print('Error in create_inflated_curv_coloring!')
        print(traceback.format_exc())


def calc_colors(vert_values, data_min, colors_ratio):
    cm = _addon().get_cm()
    if cm is None:
        return np.zeros((len(vert_values), 3))
    colors_indices = ((np.array(vert_values) - data_min) * colors_ratio).astype(int)
    # take care about values that are higher or smaller than the min and max values that were calculated (maybe using precentiles)
    colors_indices[colors_indices < 0] = 0
    colors_indices[colors_indices > 255] = 255
    verts_colors = cm[colors_indices]
    return verts_colors

# @mu.timeit
def activity_map_obj_coloring(cur_obj, vert_values, lookup, threshold, override_current_mat, data_min=None,
                              colors_ratio=None, bigger_or_equall=False):
    mesh = cur_obj.data
    scn = bpy.context.scene

    values = vert_values[:, 0] if vert_values.ndim > 1 else vert_values
    if bigger_or_equall:
        valid_verts = np.where(np.abs(values) >= threshold)[0]
    else:
        valid_verts = np.where(np.abs(values) > threshold)[0]
    colors_picked_from_cm = False
    # cm = _addon().get_cm()
    if vert_values.ndim == 1 and not data_min is None:
        verts_colors = calc_colors(vert_values, data_min, colors_ratio)
        colors_picked_from_cm = True
        # now = time.time()
        # colors_indices = ((vert_values - data_min) * colors_ratio).astype(int)
        # colors_indices[colors_indices < 0] = 0
        # colors_indices[colors_indices > 255] = 255
        # verts_colors = cm[colors_indices]
    #check if our mesh already has Vertex Colors, and if not add some... (first we need to make sure it's the active object)
    scn.objects.active = cur_obj
    cur_obj.select = True
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        mesh.vertex_colors.active_index = 1
    if not (len(mesh.vertex_colors) == 1 and 'inflated' in cur_obj.name):
        bpy.ops.mesh.vertex_color_remove()
    vcol_layer = mesh.vertex_colors.new('Col')
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        mesh.vertex_colors.active_index = 1
        mesh.vertex_colors['Col'].active_render = True
    # else:
    # vcol_layer = mesh.vertex_colors.active
    # print('cur_obj: {}, max vert in lookup: {}, vcol_layer len: {}'.format(cur_obj.name, np.max(lookup), len(vcol_layer.data)))
    for vert in valid_verts:
        x = lookup[vert]
        for loop_ind in x[x > -1]:
            d = vcol_layer.data[loop_ind]
            if colors_picked_from_cm:
                # colors = ColoringMakerPanel.cm[int(vert_values[vert] * colors_ratio)]
                colors = verts_colors[vert]
            else:
                colors = vert_values[vert, 1:]
            d.color = colors # vert_values[vert, 1:]


def color_groups_manually():
    ColoringMakerPanel.what_is_colored.add(WIC_GROUPS)
    init_activity_map_coloring('FMRI')
    labels = ColoringMakerPanel.labels_groups[bpy.context.scene.labels_groups]
    objects_names, colors, data = defaultdict(list), defaultdict(list), defaultdict(list)
    for label in labels:
        obj_type = mu.check_obj_type(label['name'])
        if obj_type is not None:
            objects_names[obj_type].append(label['name'])
            colors[obj_type].append(np.array(label['color']) / 255.0)
            data[obj_type].append(1.)
    clear_subcortical_fmri_activity()
    color_objects(objects_names, colors, data)


def color_manually():
    ColoringMakerPanel.what_is_colored.add(WIC_MANUALLY)
    init_activity_map_coloring('FMRI')
    subject_fol = mu.get_user_fol()
    objects_names, colors, data = defaultdict(list), defaultdict(list), defaultdict(list)
    values = []
    for line in mu.csv_file_reader(op.join(subject_fol, 'coloring', '{}.csv'.format(bpy.context.scene.coloring_files))):
        obj_name, color_name = line[0], line[1:4]
        if len(line) == 5:
            values.append(float(line[4]))
        if obj_name[0] == '#':
            continue
        if isinstance(color_name, list) and len(color_name) == 1:
            color_name = color_name[0]
        obj_type = mu.check_obj_type(obj_name)
        if isinstance(color_name, str) and color_name.startswith('mark'):
            import filter_panel
            filter_panel.filter_roi_func(obj_name, mark=color_name)
        else:
            if isinstance(color_name, str):
                color_rgb = cu.name_to_rgb(color_name)
            # Check if the color is already in RBG
            elif len(color_name) == 3:
                color_rgb = color_name
            else:
                print('Unrecognize color! ({})'.format(color_name))
                continue
            color_rgb = list(map(float, color_rgb))
            if obj_type is not None:
                objects_names[obj_type].append(obj_name)
                colors[obj_type].append(color_rgb)
                data[obj_type].append(1.)

    color_objects(objects_names, colors, data)
    if len(values) > 0:
        _addon().set_colorbar_max_min(np.max(values), np.min(values))
    _addon().set_colorbar_title(bpy.context.scene.coloring_files.replace('_', ' '))

    if op.isfile(op.join(subject_fol, 'coloring', '{}_legend.jpg'.format(bpy.context.scene.coloring_files))):
        cmd = '{} -m src.preproc.electrodes_preproc -s {} -a {} -f show_labeling_coloring'.format(
            bpy.context.scene.python_cmd, mu.get_user(), bpy.context.scene.atlas)
        print('Running {}'.format(cmd))
        mu.run_command_in_new_thread(cmd, False)


def color_objects(objects_names, colors, data):
    for hemi in HEMIS:
        obj_type = mu.OBJ_TYPE_CORTEX_LH if hemi=='lh' else mu.OBJ_TYPE_CORTEX_RH
        if obj_type not in objects_names or len(objects_names[obj_type]) == 0:
            continue
        labels_data = dict(data=np.array(data[obj_type]), colors=colors[obj_type], names=objects_names[obj_type])
        # print('color hemi {}: {}'.format(hemi, labels_names))
        meg_labels_coloring_hemi(labels_data, ColoringMakerPanel.faces_verts, hemi)
    clear_subcortical_regions()
    if mu.OBJ_TYPE_SUBCORTEX in objects_names:
        for region, color in zip(objects_names[mu.OBJ_TYPE_SUBCORTEX], colors[mu.OBJ_TYPE_SUBCORTEX]):
            print('color {}: {}'.format(region, color))
            color_subcortical_region(region, color)
    if mu.OBJ_TYPE_ELECTRODE in objects_names:
        for electrode, color in zip(objects_names[mu.OBJ_TYPE_ELECTRODE], colors[mu.OBJ_TYPE_ELECTRODE]):
            obj = bpy.data.objects.get(electrode)
            if obj and not obj.hide:
                object_coloring(obj, color)
    if mu.OBJ_TYPE_CEREBELLUM in objects_names:
        for cer, color in zip(objects_names[mu.OBJ_TYPE_CEREBELLUM], colors[mu.OBJ_TYPE_CEREBELLUM]):
            obj = bpy.data.objects.get(cer)
            if obj and not obj.hide:
                object_coloring(obj, color)
    bpy.context.scene.subcortical_layer = 'fmri'
    _addon().show_activity()


def color_volumetric():
    ColoringMakerPanel.what_is_colored.add(WIC_VOLUMES)
    pass


def color_subcortical_region(region_name, color):
    # obj = bpy.data.objects.get(region_name + '_meg_activity', None)
    # if not obj is None:
    #     object_coloring(obj,     color)
    cur_obj = bpy.data.objects.get(region_name + '_fmri_activity', None)
    obj_ana_fname = op.join(mu.get_user_fol(), 'subcortical', '{}.npz'.format(region_name))
    obj_lookup_fname = op.join(mu.get_user_fol(), 'subcortical', '{}_faces_verts.npy'.format(region_name))
    if not cur_obj is None and op.isfile(obj_lookup_fname):
        # todo: read only the verts number
        if not op.isfile(obj_ana_fname):
            verts, faces = mu.read_ply_file(op.join(mu.get_user_fol(), 'subcortical', '{}.ply'.format(region_name)))
            np.savez(obj_ana_fname, verts=verts, faces=faces)
        else:
            d = np.load(obj_ana_fname)
            verts =  d['verts']
        lookup = np.load(obj_lookup_fname)
        region_colors_data = np.hstack((np.array([1.]), color))
        region_colors_data = np.tile(region_colors_data, (len(verts), 1))
        activity_map_obj_coloring(cur_obj, region_colors_data, lookup, 0, True)
    else:
        if cur_obj and not 'white' in cur_obj.name.lower():
            print("Don't have the necessary files for coloring {}!".format(region_name))


def clear_subcortical_regions():
    clear_colors_from_parent_childrens('Subcortical_meg_activity_map')
    clear_subcortical_fmri_activity()


def clear_colors_from_parent_childrens(parent_object):
    parent_obj = bpy.data.objects.get(parent_object)
    if parent_obj is not None:
        for obj in parent_obj.children:
            if 'RGB' in obj.active_material.node_tree.nodes:
                obj.active_material.node_tree.nodes['RGB'].outputs['Color'].default_value = (1, 1, 1, 1)
            obj.active_material.diffuse_color = (1, 1, 1)


def default_coloring(loop_indices):
    for hemi, indices in loop_indices.items():
        cur_obj = bpy.data.objects[hemi]
        mesh = cur_obj.data
        vcol_layer = mesh.vertex_colors.active
        for loop_ind in indices:
            vcol_layer.data[loop_ind].color = [1, 1, 1]


def fmri_files_update(self, context):
    #todo: there are two frmi files list (the other one in fMRI panel)
    user_fol = mu.get_user_fol()
    for hemi in mu.HEMIS:
        fname = op.join(user_fol, 'fmri', 'fmri_{}_{}.npy'.format(bpy.context.scene.fmri_files, hemi))
        ColoringMakerPanel.fMRI[hemi] = np.load(fname)
    fmri_data_maxmin_fname = op.join(mu.get_user_fol(), 'fmri', 'fmri_activity_map_minmax_{}.pkl'.format(
        bpy.context.scene.fmri_files))
    if not op.isfile(fmri_data_maxmin_fname):
        fmri_data_maxmin_fname = op.join(mu.get_user_fol(), 'fmri', '{}_minmax.pkl'.format(
            bpy.context.scene.fmri_files))
    if op.isfile(fmri_data_maxmin_fname):
        data_min, data_max = mu.load(fmri_data_maxmin_fname)
        ColoringMakerPanel.fmri_activity_colors_ratio = 256 / (data_max - data_min)
        ColoringMakerPanel.fmri_activity_data_min = data_min
        ColoringMakerPanel.fmri_activity_data_max = data_max


def electrodes_sources_files_update(self, context):
    ColoringMakerPanel.electrodes_sources_labels_data, ColoringMakerPanel.electrodes_sources_subcortical_data = \
        get_elecctrodes_sources()


def get_elecctrodes_sources():
    labels_fname = op.join(mu.get_user_fol(), 'electrodes', '{}-{}.npz'.format(
        bpy.context.scene.electrodes_sources_files, '{hemi}'))
    subcorticals_fname = labels_fname.replace('labels', 'subcortical').replace('-{hemi}', '')
    electrodes_sources_labels_data = \
        {hemi:np.load(labels_fname.format(hemi=hemi)) for hemi in mu.HEMIS}
    electrodes_sources_subcortical_data = np.load(subcorticals_fname)
    return electrodes_sources_labels_data, electrodes_sources_subcortical_data


def color_electrodes_sources():
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES_SOURCES)
    labels_data = ColoringMakerPanel.electrodes_sources_labels_data
    subcortical_data = ColoringMakerPanel.electrodes_sources_subcortical_data
    cond_inds = np.where(subcortical_data['conditions'] == bpy.context.scene.conditions_selection)[0]
    if len(cond_inds) == 0:
        print("!!! Can't find the current condition in the data['conditions'] !!!")
        return {"FINISHED"}
    clear_subcortical_regions()
    for region, color_mat in zip(subcortical_data['names'], subcortical_data['colors']):
        color = color_mat[bpy.context.scene.frame_current, cond_inds[0], :]
        # print('electrodes source: color {} with {}'.format(region, color))
        color_subcortical_region(region, color)
    for hemi in mu.HEMIS:
        meg_labels_coloring_hemi(labels_data[hemi], ColoringMakerPanel.faces_verts, hemi, 0)


def color_eeg_helmet():
    fol = mu.get_user_fol()
    data_fname = op.join(fol, 'eeg', 'eeg_data.npy')
    data = np.load(data_fname)
    data = np.diff(data).squeeze()
    lookup = np.load(op.join(fol, 'eeg', 'eeg_faces_verts.npy'))
    threshold = 0
    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
    else:
        data_min, data_max = np.percentile(data, 3), np.percentile(data, 97)
        _addon().set_colorbar_max_min(data_max, data_min, True)
    colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_title('EEG')
    data_t = data[:, bpy.context.scene.frame_current]

    cur_obj = bpy.data.objects['eeg_helmet']
    activity_map_obj_coloring(cur_obj, data_t, lookup, threshold, True, data_min=data_min,
                              colors_ratio=colors_ratio, bigger_or_equall=False)


def color_electrodes():
    # mu.set_show_textured_solid(False)
    bpy.context.scene.show_hide_electrodes = True
    _addon().show_hide_electrodes(True)
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES)
    threshold = bpy.context.scene.coloring_threshold
    data, names, conditions = _addon().load_electrodes_data()
    norm_percs = (3, 97) #todo: add to gui
    data_max, data_min = mu.get_data_max_min(data, True, norm_percs=norm_percs, data_per_hemi=False, symmetric=True)
    colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_max_min(data_max, data_min)
    _addon().set_colorbar_title('Electordes conditions difference')
    color_objects_homogeneously(data, names, conditions, data_min, colors_ratio, threshold)
    _addon().show_electrodes()
    # for obj in bpy.data.objects['Deep_electrodes'].children:
    #     bpy.ops.object.editmode_toggle()
    #     bpy.ops.object.editmode_toggle()

    # mu.update()
    # mu.set_show_textured_solid(True)
    # _addon().change_to_rendered_brain()


    # deselect_all()
    # mu.select_hierarchy('Deep_electrodes', False)


def color_electrodes_stim():
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES_STIM)
    threshold = bpy.context.scene.coloring_threshold
    stim_fname = 'stim_electrodes_{}.npz'.format(bpy.context.scene.stim_files.replace(' ', '_'))
    stim_data_fname = op.join(mu.get_user_fol(), 'electrodes', stim_fname)
    data = np.load(stim_data_fname)
    color_objects_homogeneously(data, threshold=threshold)
    _addon().show_electrodes()
    _addon().change_to_rendered_brain()


def color_connections():
    _addon().plot_connections(_addon().connections_data(), bpy.context.scene.frame_current)


def clear_and_recolor():
    color_meg = partial(activity_map_coloring, map_type='MEG')
    color_fmri = partial(activity_map_coloring, map_type='FMRI')
    color_fmri_clusters = partial(activity_map_coloring, map_type='FMRI', clusters=True)

    wic_funcs = {
        WIC_MEG:color_meg,
        WIC_MEG_LABELS:meg_labels_coloring,
        WIC_FMRI:color_fmri,
        WIC_FMRI_CLUSTERS:color_fmri_clusters,
        WIC_ELECTRODES:color_electrodes,
        WIC_ELECTRODES_SOURCES:color_electrodes_sources,
        WIC_ELECTRODES_STIM:color_electrodes_stim,
        WIC_MANUALLY:color_manually,
        WIC_GROUPS:color_groups_manually,
        WIC_VOLUMES:color_volumetric}

    what_is_colored = ColoringMakerPanel.what_is_colored
    clear_colors()
    for wic in what_is_colored:
        wic_funcs[wic]()


class ColorEEGHelmet(bpy.types.Operator):
    bl_idname = "mmvt.eeg_helmet"
    bl_label = "mmvt eeg helmet"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_eeg_helmet()
        return {"FINISHED"}


class ColorConnections(bpy.types.Operator):
    bl_idname = "mmvt.connections_color"
    bl_label = "mmvt connections color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_connections()
        return {"FINISHED"}


class ColorElectrodes(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color"
    bl_label = "mmvt electrodes color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes()
        return {"FINISHED"}


class ColorElectrodesLabels(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color_labels"
    bl_label = "mmvt electrodes color labels"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes_sources()
        return {"FINISHED"}


class ColorElectrodesStim(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color_stim"
    bl_label = "mmvt electrodes color stim"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes_stim()
        return {"FINISHED"}


class ColorManually(bpy.types.Operator):
    bl_idname = "mmvt.man_color"
    bl_label = "mmvt man color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_manually()
        return {"FINISHED"}


class ColorVol(bpy.types.Operator):
    bl_idname = "mmvt.vol_color"
    bl_label = "mmvt vol color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_volumetric()
        return {"FINISHED"}


class ColorGroupsManually(bpy.types.Operator):
    bl_idname = "mmvt.man_groups_color"
    bl_label = "mmvt man groups color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_groups_manually()
        return {"FINISHED"}


class ColorMeg(bpy.types.Operator):
    bl_idname = "mmvt.meg_color"
    bl_label = "mmvt meg color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('MEG')
        return {"FINISHED"}


class ColorMegLabels(bpy.types.Operator):
    bl_idname = "mmvt.meg_labels_color"
    bl_label = "mmvt meg labels color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        # todo: should send also aparc_name
        meg_labels_coloring()
        return {"FINISHED"}


class ColorFmri(bpy.types.Operator):
    bl_idname = "mmvt.fmri_color"
    bl_label = "mmvt fmri color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('FMRI')
        return {"FINISHED"}


class ColorClustersFmri(bpy.types.Operator):
    bl_idname = "mmvt.fmri_clusters_color"
    bl_label = "mmvt fmri clusters color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('FMRI', clusters=True)
        return {"FINISHED"}


class ClearColors(bpy.types.Operator):
    bl_idname = "mmvt.colors_clear"
    bl_label = "mmvt colors clear"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        clear_colors()
        return {"FINISHED"}


def clear_colors():
    clear_cortex()
    clear_subcortical_fmri_activity()
    for root in ['Subcortical_meg_activity_map', 'Deep_electrodes']:
        clear_colors_from_parent_childrens(root)
    ColoringMakerPanel.what_is_colored = set()


bpy.types.Scene.coloring_fmri = bpy.props.BoolProperty(default=True, description="Plot FMRI")
bpy.types.Scene.coloring_electrodes = bpy.props.BoolProperty(default=False, description="Plot Deep electrodes")
bpy.types.Scene.coloring_threshold = bpy.props.FloatProperty(default=0.5, min=0, description="")
bpy.types.Scene.fmri_files = bpy.props.EnumProperty(items=[('no', 'no', '', 1)], description="fMRI files")
bpy.types.Scene.electrodes_sources_files = bpy.props.EnumProperty(items=[], description="electrodes sources files")
bpy.types.Scene.coloring_files = bpy.props.EnumProperty(items=[], description="Coloring files")
bpy.types.Scene.vol_coloring_files = bpy.props.EnumProperty(items=[], description="Coloring volumetric files")
bpy.types.Scene.coloring_both_pial_and_inflated = bpy.props.BoolProperty(default=False, description="")
bpy.types.Scene.coloring_meg_subcorticals = bpy.props.BoolProperty(default=False, description="")


class ColoringMakerPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Activity Maps"
    addon = None
    fMRI = {}
    fMRI_clusters = {}
    labels_vertices = {}
    electrodes_sources_labels_data = None
    electrodes_sources_subcortical_data = None
    what_is_colored = set()
    fmri_activity_data_min, fmri_activity_data_max, fmri_activity_colors_ratio = None, None, None

    def draw(self, context):
        layout = self.layout
        user_fol = mu.get_user_fol()
        aparc_name = bpy.context.scene.atlas
        faces_verts_exist = mu.hemi_files_exists(op.join(user_fol, 'faces_verts_{hemi}.npy'))
        fmri_files = glob.glob(op.join(user_fol, 'fmri', '*_lh.npy'))  # mu.hemi_files_exists(op.join(user_fol, 'fmri_{hemi}.npy'))
        # fmri_clusters_files_exist = mu.hemi_files_exists(op.join(user_fol, 'fmri', 'fmri_clusters_{hemi}.npy'))
        meg_files_exist = mu.hemi_files_exists(op.join(user_fol, 'activity_map_{hemi}', 't0.npy'))
        meg_data_maxmin_file_exist = op.isfile(op.join(mu.get_user_fol(), 'meg_activity_map_minmax.pkl'))
        meg_labels_files_exist = op.isfile(op.join(user_fol, 'labels_vertices_{}.pkl'.format(aparc_name))) and \
            mu.hemi_files_exists(op.join(user_fol, 'meg_labels_coloring_{hemi}.npz'))
        # electrodes_files_exist = op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_data_{}.npz'.format(
        #     'avg' if bpy.context.scene.selection_type == 'conds' else 'diff'))) or \
        #     op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_data_{}_data.npy'.format(
        #     'avg' if bpy.context.scene.selection_type == 'conds' else 'diff')))
        electrodes_files_exist = op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_data_diff.npz')) or \
                                 op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_data_diff_data.npy'))
        electrodes_stim_files_exist = len(glob.glob(op.join(
            mu.get_user_fol(), 'electrodes', 'stim_electrodes_*.npz'))) > 0
        electrodes_labels_files_exist = len(glob.glob(op.join(
            mu.get_user_fol(), 'electrodes', '*_labels_*.npz'))) > 0 and \
            len(glob.glob(op.join(mu.get_user_fol(), 'electrodes', '*_subcortical_*.npz'))) > 0
        manually_color_files_exist = len(glob.glob(op.join(user_fol, 'coloring', '*.csv'))) > 0
        manually_groups_file_exist = op.isfile(op.join(mu.get_parent_fol(user_fol),
            '{}_groups.csv'.format(bpy.context.scene.atlas)))
        if _addon() is None:
            connections_files_exit = False
        else:
            connections_files_exit = _addon().connections_exist() and not _addon().connections_data is None
        # volumetric_coloring_files_exist = len(glob.glob(op.join(user_fol, 'coloring', 'volumetric', '*.csv')))
        layout.prop(context.scene, 'coloring_threshold', text="Threshold")
        layout.prop(context.scene, 'coloring_both_pial_and_inflated', text="Both pial & inflated")
        if faces_verts_exist:
            if meg_files_exist and meg_data_maxmin_file_exist:
                layout.operator(ColorMeg.bl_idname, text="Plot MEG ", icon='POTATO')
                if op.isfile(op.join(mu.get_user_fol(), 'subcortical_meg_activity.npz')):
                    layout.prop(context.scene, 'coloring_meg_subcorticals', text="Plot also subcorticals")
            # if meg_labels_files_exist:
            #     layout.operator(ColorMegLabels.bl_idname, text="Plot MEG Labels ", icon='POTATO')
            if len(fmri_files) > 0:
                layout.prop(context.scene, "fmri_files", text="")
                layout.operator(ColorFmri.bl_idname, text="Plot fMRI ", icon='POTATO')
            if manually_color_files_exist:
                layout.prop(context.scene, "coloring_files", text="")
                layout.operator(ColorManually.bl_idname, text="Color Manually", icon='POTATO')
            if manually_groups_file_exist:
                layout.prop(context.scene, 'labels_groups', text="")
                layout.operator(ColorGroupsManually.bl_idname, text="Color Groups", icon='POTATO')
            # if volumetric_coloring_files_exist:
            #     layout.prop(context.scene, "vol_coloring_files", text="")
            #     layout.operator(ColorVol.bl_idname, text="Color Volumes", icon='POTATO')
        # if not bpy.data.objects.get('eeg_helmet', None) is None:
        #     layout.operator(ColorEEGHelmet.bl_idname, text="Plot EEG Helmet", icon='POTATO')
        if electrodes_files_exist:
            layout.operator(ColorElectrodes.bl_idname, text="Plot Electrodes", icon='POTATO')
        if electrodes_labels_files_exist:
            layout.prop(context.scene, "electrodes_sources_files", text="")
            layout.operator(ColorElectrodesLabels.bl_idname, text="Plot Electrodes Sources", icon='POTATO')
        if electrodes_stim_files_exist:
            layout.operator(ColorElectrodesStim.bl_idname, text="Plot Electrodes Stimulation", icon='POTATO')
        if connections_files_exit:
            layout.operator(ColorConnections.bl_idname, text="Plot Connections", icon='POTATO')
        layout.operator(ClearColors.bl_idname, text="Clear", icon='PANEL_CLOSE')


def get_fMRI_activity(hemi, clusters=False):
    if clusters:
        f = [c for c in ColoringMakerPanel.fMRI_clusters if c['hemi'] == hemi]
    else:
        f = ColoringMakerPanel.fMRI[hemi]
    return f
    # return ColoringMakerPanel.fMRI_clusters[hemi] if clusters else ColoringMakerPanel.fMRI[hemi]


def get_faces_verts():
    return ColoringMakerPanel.faces_verts


def read_groups_labels(colors):
    groups_fname = op.join(mu.get_parent_fol(mu.get_user_fol()), '{}_groups.csv'.format(bpy.context.scene.atlas))
    if not op.isfile(groups_fname):
        return {}
    groups = defaultdict(list) # OrderedDict() # defaultdict(list)
    color_ind = 0
    for line in mu.csv_file_reader(groups_fname):
        group_name = line[0]
        group_color = line[1]
        labels = line[2:]
        if group_name[0] == '#':
            continue
        groups[group_name] = []
        for label in labels:
            # group_color = cu.name_to_rgb(colors[color_ind])
            groups[group_name].append(dict(name=label, color=cu.name_to_rgb(group_color)))
            color_ind += 1
    order_groups = OrderedDict()
    groups_names = sorted(list(groups.keys()))
    for group_name in groups_names:
        order_groups[group_name] = groups[group_name]
    return order_groups


def init(addon):
    from random import shuffle
    ColoringMakerPanel.addon = addon
    user_fol = mu.get_user_fol()
    ColoringMakerPanel.faces_verts = None
    labels_vertices_fname = op.join(user_fol, 'labels_vertices_{}.pkl'.format(bpy.context.scene.atlas))
    if not op.isfile(labels_vertices_fname):
        print("!!! Can't find {}!".format('labels_vertices_{}.pkl'.format(bpy.context.scene.atlas)))
        return None
    labels_names, labels_vertices = mu.load(labels_vertices_fname)
    ColoringMakerPanel.labels_vertices = dict(labels_names=labels_names, labels_vertices=labels_vertices)
    ColoringMakerPanel.max_labels_vertices_num = {}

    meg_files_exist = mu.hemi_files_exists(op.join(user_fol, 'activity_map_{hemi}', 't0.npy'))
    meg_data_maxmin_fname = op.join(mu.get_user_fol(), 'meg_activity_map_minmax.pkl')
    if meg_files_exist and op.isfile(meg_data_maxmin_fname):
        data_min, data_max = mu.load(meg_data_maxmin_fname)
        ColoringMakerPanel.meg_activity_colors_ratio = 256 / (data_max - data_min)
        ColoringMakerPanel.meg_activity_data_min = data_min
        ColoringMakerPanel.meg_activity_data_max = data_max
        print('data meg: {}-{}'.format(data_min, data_max))
        _addon().set_colorbar_max_min(data_max, data_min, True)
        _addon().set_colorbar_title('MEG')

    fmri_files = glob.glob(op.join(user_fol, 'fmri', 'fmri_*_lh.npy'))
    if len(fmri_files) > 0:
        files_names = [mu.namebase(fname)[5:-3] for fname in fmri_files]
        clusters_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.fmri_files = bpy.props.EnumProperty(
            items=clusters_items, description="fMRI files", update=fmri_files_update)
        bpy.context.scene.fmri_files = files_names[0]
        for hemi in mu.HEMIS:
            ColoringMakerPanel.fMRI[hemi] = np.load('{}_{}.npy'.format(fmri_files[0][:-7], hemi))
        # Check separately for each contrast
        fmri_data_maxmin_fname = op.join(mu.get_user_fol(), 'fmri', 'fmri_activity_map_minmax.pkl')
        if op.isfile(fmri_data_maxmin_fname):
            data_min, data_max = mu.load(fmri_data_maxmin_fname)
            ColoringMakerPanel.fmri_activity_colors_ratio = 256 / (data_max - data_min)
            ColoringMakerPanel.fmri_activity_data_min = data_min
            ColoringMakerPanel.fmri_activity_data_max = data_max

    electrodes_source_files = glob.glob(op.join(user_fol, 'electrodes', '*_labels_*-rh.npz'))
    if len(electrodes_source_files) > 0:
        files_names = [mu.namebase(fname)[:-len('-rh')] for fname in electrodes_source_files]
        items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.electrodes_sources_files = bpy.props.EnumProperty(
            items=items, description="electrodes sources", update=electrodes_sources_files_update)
        bpy.context.scene.electrodes_sources_files = files_names[0]

    mu.make_dir(op.join(user_fol, 'coloring'))
    manually_color_files = glob.glob(op.join(user_fol, 'coloring', '*.csv'))
    if len(manually_color_files) > 0:
        files_names = [mu.namebase(fname) for fname in manually_color_files]
        coloring_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.coloring_files = bpy.props.EnumProperty(items=coloring_items, description="Coloring files")
        bpy.context.scene.coloring_files = files_names[0]
    vol_color_files = glob.glob(op.join(user_fol, 'coloring', 'volumetric', '*.csv'))
    if len(vol_color_files) > 0:
        files_names = [mu.namebase(fname) for fname in vol_color_files]
        coloring_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.vol_coloring_files = bpy.props.EnumProperty(
            items=coloring_items, description="Volumetric Coloring files")
        bpy.context.scene.vol_coloring_files = files_names[0]

    ColoringMakerPanel.colors = list(set(list(cu.NAMES_TO_HEX.keys())) - set(['black']))
    shuffle(ColoringMakerPanel.colors)
    ColoringMakerPanel.labels_groups = read_groups_labels(ColoringMakerPanel.colors)
    if len(ColoringMakerPanel.labels_groups) > 0:
        groups_items = [(gr, gr, '', ind) for ind, gr in enumerate(list(ColoringMakerPanel.labels_groups.keys()))]
        bpy.types.Scene.labels_groups = bpy.props.EnumProperty(
            items=groups_items, description="Groups")

    ColoringMakerPanel.faces_verts = load_faces_verts()
    bpy.context.scene.coloring_meg_subcorticals = False
    # ColoringMakerPanel.cm = np.load(op.join(mu.file_fol(), 'color_maps', 'BuPu_YlOrRd.npy'))
    register()


def register():
    try:
        unregister()
        bpy.utils.register_class(ColorElectrodes)
        bpy.utils.register_class(ColorElectrodesStim)
        bpy.utils.register_class(ColorElectrodesLabels)
        bpy.utils.register_class(ColorManually)
        bpy.utils.register_class(ColorVol)
        bpy.utils.register_class(ColorGroupsManually)
        bpy.utils.register_class(ColorMeg)
        bpy.utils.register_class(ColorMegLabels)
        bpy.utils.register_class(ColorFmri)
        bpy.utils.register_class(ColorClustersFmri)
        bpy.utils.register_class(ColorEEGHelmet)
        bpy.utils.register_class(ColorConnections)
        bpy.utils.register_class(ClearColors)
        bpy.utils.register_class(ColoringMakerPanel)
        # print('Freeview Panel was registered!')
    except:
        print("Can't register Freeview Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(ColorElectrodes)
        bpy.utils.unregister_class(ColorElectrodesStim)
        bpy.utils.unregister_class(ColorElectrodesLabels)
        bpy.utils.unregister_class(ColorManually)
        bpy.utils.unregister_class(ColorVol)
        bpy.utils.unregister_class(ColorGroupsManually)
        bpy.utils.unregister_class(ColorMeg)
        bpy.utils.unregister_class(ColorMegLabels)
        bpy.utils.unregister_class(ColorFmri)
        bpy.utils.unregister_class(ColorClustersFmri)
        bpy.utils.unregister_class(ColorEEGHelmet)
        bpy.utils.unregister_class(ColorConnections)
        bpy.utils.unregister_class(ClearColors)
        bpy.utils.unregister_class(ColoringMakerPanel)
    except:
        pass
        # print("Can't unregister Freeview Panel!")

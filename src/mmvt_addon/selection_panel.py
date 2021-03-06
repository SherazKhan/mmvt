import bpy
import mmvt_utils as mu
import numpy as np
import colors_utils as cu
import connections_panel
import electrodes_panel
import os.path as op


def _addon():
    return SelectionMakerPanel.addon


def conditions_diff():
    return bpy.context.scene.selection_type == 'diff'


def both_conditions():
    return bpy.context.scene.selection_type == 'conds'


def spec_condition():
    return bpy.context.scene.selection_type == 'spec_cond'


def fit_selection(context=None):
    mu.view_all_in_graph_editor(context)


def deselect_all():
    for obj in bpy.data.objects:
        obj.select = False
    if bpy.data.objects.get(' '):
        bpy.data.objects[' '].select = True
        bpy.context.scene.objects.active = bpy.data.objects[' ']


def meg_data_loaded():
    parent_obj = bpy.data.objects.get('Brain')
    if parent_obj is None:
        return False
    else:
        parent_data = mu.count_fcurves(parent_obj) > 0
        labels = bpy.data.objects['Cortex-lh'].children + bpy.data.objects['Cortex-rh'].children
        labels_data = mu.count_fcurves(labels) > 0
        return parent_data or labels_data


def fmri_data_loaded():
    fmri_parent_obj = bpy.data.objects.get('fMRI')
    return mu.count_fcurves(fmri_parent_obj) > 0


def select_roi(roi_name):
    roi = bpy.data.objects.get(roi_name)
    if roi is None:
        return

    # check if MEG data is loaded and attahced to the obj
    if mu.count_fcurves(roi) > 0:
        roi.select  = True
        mu.change_fcurves_colors(roi)
    else:
        # Check if dynamic fMRI data is loaded
        fmri_parent_obj = bpy.data.objects.get('fMRI')
        fcurves = mu.get_fcurves(fmri_parent_obj)
        for fcurve in fcurves:
            if mu.get_fcurve_name(fcurve) == roi_name:
                fcurve.hide = False
                fmri_parent_obj.select = True
            else:
                fcurve.hide = True


def select_all_rois():
    fmri_parent = bpy.data.objects.get('fMRI')
    if mu.count_fcurves(bpy.data.objects['Brain']) > 0:
        bpy.context.scene.filter_curves_type = 'MEG'
        select_brain_objects('Brain', bpy.data.objects['Cortex-lh'].children + bpy.data.objects['Cortex-rh'].children)
    elif not fmri_parent is None:
        bpy.context.scene.filter_curves_type = 'fMRI'
        select_brain_objects('fMRI')
        # fmri_parent.select = True
        # mu.show_hide_obj_and_fcurves(fmri_parent, True)


def select_only_subcorticals():
    bpy.context.scene.filter_curves_type = 'MEG'
    select_brain_objects('Subcortical_structures')


def select_all_eeg():
    bpy.context.scene.filter_curves_type = 'EEG'
    select_brain_objects('EEG_electrodes')


def select_all_electrodes():
    bpy.context.scene.filter_curves_type = 'Electrodes'
    select_brain_objects('Deep_electrodes')


def select_all_connections():
    connection_parent_name = _addon().get_parent_obj_name()
    select_brain_objects(connection_parent_name)


def conditions_selection_update(self, context):
    mu.filter_graph_editor(bpy.context.scene.conditions_selection)
    _addon().clear_and_recolor()


def select_brain_objects(parent_obj_name, children=None):
    if children is None:
        children = bpy.data.objects[parent_obj_name].children
    parent_obj = bpy.data.objects[parent_obj_name]
    children_have_fcurves = mu.count_fcurves(children) > 0
    if bpy.context.scene.selection_type == 'diff' or not children_have_fcurves:
        if parent_obj.animation_data is None:
            print('parent_obj.animation_data is None!')
        else:
            mu.show_hide_obj_and_fcurves(children, False)
            parent_obj.select = True
            mu.show_hide_obj_and_fcurves(parent_obj, True)
            # for fcurve in parent_obj.animation_data.action.fcurves:
            #     fcurve.hide = False
            #     fcurve.select = True
    else:
        mu.show_hide_obj_and_fcurves(children, True)
        parent_obj.select = False
    mu.view_all_in_graph_editor()


def set_conditions_enum(conditions):
    conditions = mu.unique_save_order(conditions)
    selection_items = [(c, '{}'.format(c), '', ind) for ind, c in enumerate(conditions)]
    try:
        bpy.types.Scene.conditions_selection = bpy.props.EnumProperty(
            items=selection_items, description="Condition Selection", update=conditions_selection_update)
    except:
        print("Cant register conditions_selection!")


def set_selection_type(selection_type):
    bpy.context.scene.selection_type = selection_type


class SelectAllRois(bpy.types.Operator):
    bl_idname = "mmvt.roi_selection"
    bl_label = "select2 ROIs"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        select_all_rois()
        mu.view_all_in_graph_editor(context)
        if bpy.context.scene.selection_type == 'diff':
            mu.change_fcurves_colors([bpy.data.objects['Brain']])
        else:
            corticals_labels = mu.get_corticals_labels()
            mu.change_fcurves_colors(corticals_labels)
        return {"FINISHED"}


class SelectAllSubcorticals(bpy.types.Operator):
    bl_idname = "mmvt.subcorticals_selection"
    bl_label = "select only subcorticals"
    bl_options = {"UNDO"}

    def invoke(self, context, event=None):
        select_only_subcorticals()
        mu.view_all_in_graph_editor(context)
        if bpy.context.scene.selection_type == 'diff':
            mu.change_fcurves_colors([bpy.data.objects['Subcortical_structures']])
        else:
            mu.change_fcurves_colors(bpy.data.objects['Subcortical_structures'].children)
        return {"FINISHED"}


class SelectAllEEG(bpy.types.Operator):
    bl_idname = "mmvt.eeg_selection"
    bl_label = "select eeg"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        select_all_eeg()
        mu.unfilter_graph_editor()
        # if bpy.context.scene.selection_type == 'diff':
        #     mu.change_fcurves_colors([bpy.data.objects['Deep_electrodes']])
        # elif bpy.context.scene.selection_type == 'spec_cond':
        #     mu.filter_graph_editor(bpy.context.scene.conditions_selection)
        # else:
        mu.change_fcurves_colors(bpy.data.objects['EEG_electrodes'].children)
        mu.view_all_in_graph_editor(context)
        return {"FINISHED"}


class SelectAllElectrodes(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_selection"
    bl_label = "select2 Electrodes"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        select_all_electrodes()
        mu.unfilter_graph_editor()
        if bpy.context.scene.selection_type == 'diff':
            mu.change_fcurves_colors([bpy.data.objects['Deep_electrodes']])
        elif bpy.context.scene.selection_type == 'spec_cond':
            mu.filter_graph_editor(bpy.context.scene.conditions_selection)
        else:
            mu.change_fcurves_colors(bpy.data.objects['Deep_electrodes'].children)
        mu.view_all_in_graph_editor(context)
        return {"FINISHED"}


class SelectAllConnections(bpy.types.Operator):
    bl_idname = "mmvt.connections_selection"
    bl_label = "select connections"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        select_all_connections()
        mu.view_all_in_graph_editor(context)
        return {"FINISHED"}


class ClearSelection(bpy.types.Operator):
    bl_idname = "mmvt.clear_selection"
    bl_label = "deselect all"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        for obj in bpy.data.objects:
            obj.select = False
        if bpy.data.objects.get(' '):
            bpy.data.objects[' '].select = True
            bpy.context.scene.objects.active = bpy.data.objects[' ']

        return {"FINISHED"}


class FitSelection(bpy.types.Operator):
    bl_idname = "mmvt.fit_selection"
    bl_label = "Fit selection"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        fit_selection(context)
        return {"FINISHED"}


class PrevWindow(bpy.types.Operator):
    bl_idname = "mmvt.prev_window"
    bl_label = "prev window"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.current_window_selection -= 1
        change_window()
        return {"FINISHED"}


class NextWindow(bpy.types.Operator):
    bl_idname = "mmvt.next_window"
    bl_label = "next window"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.current_window_selection += 1
        change_window()
        return {"FINISHED"}


class JumpToWindow(bpy.types.Operator):
    bl_idname = "mmvt.jump_to_window"
    bl_label = "jump to window"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        change_window()
        return {"FINISHED"}


def change_window():
    import time
    # todo: check what kind of data is displayed in the graph panel
    data_type = 'eeg'
    change = True
    if data_type == 'eeg':
        now = time.time()
        data, meta = _addon().eeg_data_and_meta()
        obj_name = 'EEG_electrodes'
        ch_names = meta['names']
        points_in_sec = int(1 / meta['dt'])
        window_len = get_window_length(obj_name)
        new_point_in_time = bpy.context.scene.current_window_selection * points_in_sec
        #todo: add a factor field
        factor = 1000
        new_data = data[:, new_point_in_time:new_point_in_time + window_len - 1] * factor
        print('{} took {:.6f}s'.format('loading', time.time() - now))

    else:
        change = False
    if change:
        mu.change_fcurves(obj_name, new_data, ch_names)
        bpy.data.scenes['Scene'].frame_preview_start = 0
        bpy.data.scenes['Scene'].frame_preview_end = window_len


def get_window_length(obj_name):
    try:
        parent_obj = bpy.data.objects[obj_name]
        fcurve = parent_obj.animation_data.action.fcurves[0]
        N = len(fcurve.keyframe_points)
    except:
        N = 2000
    return N


bpy.types.Scene.selection_type = bpy.props.EnumProperty(
    items=[("diff", "Conditions difference", "", 1), ("conds", "All conditions", "", 2)])
           # ("spec_cond", "Specific condition", "", 3)], description="Selection type")
bpy.types.Scene.conditions_selection = bpy.props.EnumProperty(items=[], description="Condition Selection",
                                                              update=conditions_selection_update)
bpy.types.Scene.current_window_selection = bpy.props.IntProperty(min=0, default=0, max=1000, description="")
bpy.types.Scene.selected_modlity = bpy.props.EnumProperty(items=[])


def get_dt():
    #todo: check what is in the graph panel
    data_type = 'eeg'
    if data_type == 'eeg':
        _, meta = _addon().eeg_data_and_meta()
        return meta['dt'] if meta and 'dt' in meta else None
    else:
        return None


class SelectionMakerPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Selection"
    addon = None
    modalities_num = 0

    @staticmethod
    def draw(self, context):
        layout = self.layout
        # if bpy.context.scene.selection_type == 'spec_cond':
        #     layout.prop(context.scene, "conditions_selection", text="")
        # labels_data = ''
        # fmri_parent = bpy.data.objects.get('fMRI')
        # if mu.count_fcurves(bpy.data.objects['Brain']) > 0:
        #     labels_data = 'MEG'
        # elif not fmri_parent is None:
        #     labels_data = 'fMRI'
        layout.prop(context.scene, "selection_type", text="")
        sm = bpy.context.scene.selected_modlity
        if SelectionMakerPanel.modalities_num > 1:
            layout.prop(context.scene, 'selected_modlity', text='')
        if meg_data_loaded() or fmri_data_loaded():
            layout.operator(SelectAllRois.bl_idname, text="Cortical labels ({})".format(sm), icon='BORDER_RECT')
        layout.operator(SelectAllSubcorticals.bl_idname, text="Subcorticals ({})".format(sm), icon = 'BORDER_RECT')
        if bpy.data.objects.get(electrodes_panel.PARENT_OBJ):
            layout.operator(SelectAllElectrodes.bl_idname, text="Electrodes", icon='BORDER_RECT')
        if bpy.data.objects.get('EEG_electrodes'):
            layout.operator(SelectAllEEG.bl_idname, text="EEG", icon='BORDER_RECT')
        if bpy.data.objects.get(_addon().get_parent_obj_name()) and \
                bpy.data.objects[_addon().get_parent_obj_name()].animation_data:
            layout.operator(SelectAllConnections.bl_idname, text="Connections", icon='BORDER_RECT')
        layout.operator(ClearSelection.bl_idname, text="Deselect all", icon='PANEL_CLOSE')
        layout.operator(FitSelection.bl_idname, text="Fit graph window", icon='MOD_ARMATURE')

        # if not SelectionMakerPanel.dt is None:
        #     points_in_sec = int(1 / SelectionMakerPanel.dt)
        #     window_from = bpy.context.scene.current_window_selection * points_in_sec / 1000
        #     window_to =  window_from + points_in_sec * 2 / 1000
        #
        #     layout.label(text='From {:.2f}s to {:.2f}s'.format(window_from, window_to))
        #     row = layout.row(align=True)
        #     # row.operator(Play.bl_idname, text="", icon='PLAY' if not PlayPanel.is_playing else 'PAUSE')
        #     row.operator(PrevWindow.bl_idname, text="", icon='PREV_KEYFRAME')
        #     row.operator(NextWindow.bl_idname, text="", icon='NEXT_KEYFRAME')
        #     row.prop(context.scene, 'current_window_selection', text='window')
        #     row.operator(JumpToWindow.bl_idname, text='Jump', icon='DRIVER')


def init(addon):
    SelectionMakerPanel.addon = addon
    SelectionMakerPanel.dt = get_dt()
    modalities_itesm = []
    if meg_data_loaded():
        modalities_itesm.append(('MEG', 'MEG', '', 0))
    if fmri_data_loaded():
        modalities_itesm.append(('fMRI', 'fMRI', '', 1))
    SelectionMakerPanel.modalities_num = len(modalities_itesm)
    bpy.types.Scene.selected_modlity = bpy.props.EnumProperty(items=modalities_itesm)
    register()


def register():
    try:
        unregister()
        bpy.utils.register_class(SelectionMakerPanel)
        bpy.utils.register_class(FitSelection)
        bpy.utils.register_class(ClearSelection)
        bpy.utils.register_class(SelectAllConnections)
        bpy.utils.register_class(SelectAllElectrodes)
        bpy.utils.register_class(SelectAllEEG)
        bpy.utils.register_class(SelectAllSubcorticals)
        bpy.utils.register_class(SelectAllRois)
        bpy.utils.register_class(NextWindow)
        bpy.utils.register_class(PrevWindow)
        bpy.utils.register_class(JumpToWindow)
        # print('Selection Panel was registered!')
    except:
        print("Can't register Selection Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(SelectionMakerPanel)
        bpy.utils.unregister_class(FitSelection)
        bpy.utils.unregister_class(ClearSelection)
        bpy.utils.unregister_class(SelectAllConnections)
        bpy.utils.unregister_class(SelectAllElectrodes)
        bpy.utils.unregister_class(SelectAllEEG)
        bpy.utils.unregister_class(SelectAllSubcorticals)
        bpy.utils.unregister_class(SelectAllRois)
        bpy.utils.unregister_class(NextWindow)
        bpy.utils.unregister_class(PrevWindow)
        bpy.utils.unregister_class(JumpToWindow)
    except:
        pass

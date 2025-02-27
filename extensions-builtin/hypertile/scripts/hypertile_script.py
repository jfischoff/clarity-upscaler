import hypertile
from modules import scripts, script_callbacks, shared
# from hypertile_xyz import add_axis_options

xyz_grid = [x for x in scripts.scripts_data if x.script_class.__module__ == "xyz_grid.py"][0].module

def int_applier(value_name:str, min_range:int = -1, max_range:int = -1):
    """
    Returns a function that applies the given value to the given value_name in opts.data.
    """
    def validate(value_name:str, value:str):
        value = int(value)
        # validate value
        if not min_range == -1:
            assert value >= min_range, f"Value {value} for {value_name} must be greater than or equal to {min_range}"
        if not max_range == -1:
            assert value <= max_range, f"Value {value} for {value_name} must be less than or equal to {max_range}"
    def apply_int(p, x, xs):
        validate(value_name, x)
        opts.data[value_name] = int(x)
    return apply_int

def bool_applier(value_name:str):
    """
    Returns a function that applies the given value to the given value_name in opts.data.
    """
    def validate(value_name:str, value:str):
        assert value.lower() in ["true", "false"], f"Value {value} for {value_name} must be either true or false"
    def apply_bool(p, x, xs):
        validate(value_name, x)
        value_boolean = x.lower() == "true"
        opts.data[value_name] = value_boolean
    return apply_bool

def add_axis_options():
    extra_axis_options = [
        xyz_grid.AxisOption("[Hypertile] Unet First pass Enabled", str, bool_applier("hypertile_enable_unet"), choices=xyz_grid.boolean_choice(reverse=True)),
        xyz_grid.AxisOption("[Hypertile] Unet Second pass Enabled", str, bool_applier("hypertile_enable_unet_secondpass"), choices=xyz_grid.boolean_choice(reverse=True)),
        xyz_grid.AxisOption("[Hypertile] Unet Max Depth", int, int_applier("hypertile_max_depth_unet", 0, 3), choices=lambda: [str(x) for x in range(4)]),
        xyz_grid.AxisOption("[Hypertile] Unet Max Tile Size", int, int_applier("hypertile_max_tile_unet", 0, 512)),
        xyz_grid.AxisOption("[Hypertile] Unet Swap Size", int, int_applier("hypertile_swap_size_unet", 0, 64)),
        xyz_grid.AxisOption("[Hypertile] VAE Enabled", str, bool_applier("hypertile_enable_vae"), choices=xyz_grid.boolean_choice(reverse=True)),
        xyz_grid.AxisOption("[Hypertile] VAE Max Depth", int, int_applier("hypertile_max_depth_vae", 0, 3), choices=lambda: [str(x) for x in range(4)]),
        xyz_grid.AxisOption("[Hypertile] VAE Max Tile Size", int, int_applier("hypertile_max_tile_vae", 0, 512)),
        xyz_grid.AxisOption("[Hypertile] VAE Swap Size", int, int_applier("hypertile_swap_size_vae", 0, 64)),
    ]
    set_a = {opt.label for opt in xyz_grid.axis_options}
    set_b = {opt.label for opt in extra_axis_options}
    if set_a.intersection(set_b):
        return

    xyz_grid.axis_options.extend(extra_axis_options)

class ScriptHypertile(scripts.Script):
    name = "Hypertile"

    def title(self):
        return self.name

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p, *args):
        hypertile.set_hypertile_seed(p.all_seeds[0])

        configure_hypertile(p.width, p.height, enable_unet=shared.opts.hypertile_enable_unet)

        self.add_infotext(p)

    def before_hr(self, p, *args):

        enable = shared.opts.hypertile_enable_unet_secondpass or shared.opts.hypertile_enable_unet

        # exclusive hypertile seed for the second pass
        if enable:
            hypertile.set_hypertile_seed(p.all_seeds[0])

        configure_hypertile(p.hr_upscale_to_x, p.hr_upscale_to_y, enable_unet=enable)

        if enable and not shared.opts.hypertile_enable_unet:
            p.extra_generation_params["Hypertile U-Net second pass"] = True

            self.add_infotext(p, add_unet_params=True)

    def add_infotext(self, p, add_unet_params=False):
        def option(name):
            value = getattr(shared.opts, name)
            default_value = shared.opts.get_default(name)
            return None if value == default_value else value

        if shared.opts.hypertile_enable_unet:
            p.extra_generation_params["Hypertile U-Net"] = True

        if shared.opts.hypertile_enable_unet or add_unet_params:
            p.extra_generation_params["Hypertile U-Net max depth"] = option('hypertile_max_depth_unet')
            p.extra_generation_params["Hypertile U-Net max tile size"] = option('hypertile_max_tile_unet')
            p.extra_generation_params["Hypertile U-Net swap size"] = option('hypertile_swap_size_unet')

        if shared.opts.hypertile_enable_vae:
            p.extra_generation_params["Hypertile VAE"] = True
            p.extra_generation_params["Hypertile VAE max depth"] = option('hypertile_max_depth_vae')
            p.extra_generation_params["Hypertile VAE max tile size"] = option('hypertile_max_tile_vae')
            p.extra_generation_params["Hypertile VAE swap size"] = option('hypertile_swap_size_vae')


def configure_hypertile(width, height, enable_unet=True):
    hypertile.hypertile_hook_model(
        shared.sd_model.first_stage_model,
        width,
        height,
        swap_size=shared.opts.hypertile_swap_size_vae,
        max_depth=shared.opts.hypertile_max_depth_vae,
        tile_size_max=shared.opts.hypertile_max_tile_vae,
        enable=shared.opts.hypertile_enable_vae,
    )

    hypertile.hypertile_hook_model(
        shared.sd_model.model,
        width,
        height,
        swap_size=shared.opts.hypertile_swap_size_unet,
        max_depth=shared.opts.hypertile_max_depth_unet,
        tile_size_max=shared.opts.hypertile_max_tile_unet,
        enable=enable_unet,
        is_sdxl=shared.sd_model.is_sdxl
    )


def on_ui_settings():
    import gradio as gr

    options = {
        "hypertile_explanation": shared.OptionHTML("""
    <a href='https://github.com/tfernd/HyperTile'>Hypertile</a> optimizes the self-attention layer within U-Net and VAE models,
    resulting in a reduction in computation time ranging from 1 to 4 times. The larger the generated image is, the greater the
    benefit.
    """),

        "hypertile_enable_unet": shared.OptionInfo(False, "Enable Hypertile U-Net", infotext="Hypertile U-Net").info("enables hypertile for all modes, including hires fix second pass; noticeable change in details of the generated picture"),
        "hypertile_enable_unet_secondpass": shared.OptionInfo(False, "Enable Hypertile U-Net for hires fix second pass", infotext="Hypertile U-Net second pass").info("enables hypertile just for hires fix second pass - regardless of whether the above setting is enabled"),
        "hypertile_max_depth_unet": shared.OptionInfo(3, "Hypertile U-Net max depth", gr.Slider, {"minimum": 0, "maximum": 3, "step": 1}, infotext="Hypertile U-Net max depth").info("larger = more neural network layers affected; minor effect on performance"),
        "hypertile_max_tile_unet": shared.OptionInfo(256, "Hypertile U-Net max tile size", gr.Slider, {"minimum": 0, "maximum": 512, "step": 16}, infotext="Hypertile U-Net max tile size").info("larger = worse performance"),
        "hypertile_swap_size_unet": shared.OptionInfo(3, "Hypertile U-Net swap size", gr.Slider, {"minimum": 0, "maximum": 64, "step": 1}, infotext="Hypertile U-Net swap size"),

        "hypertile_enable_vae": shared.OptionInfo(False, "Enable Hypertile VAE", infotext="Hypertile VAE").info("minimal change in the generated picture"),
        "hypertile_max_depth_vae": shared.OptionInfo(3, "Hypertile VAE max depth", gr.Slider, {"minimum": 0, "maximum": 3, "step": 1}, infotext="Hypertile VAE max depth"),
        "hypertile_max_tile_vae": shared.OptionInfo(128, "Hypertile VAE max tile size", gr.Slider, {"minimum": 0, "maximum": 512, "step": 16}, infotext="Hypertile VAE max tile size"),
        "hypertile_swap_size_vae": shared.OptionInfo(3, "Hypertile VAE swap size ", gr.Slider, {"minimum": 0, "maximum": 64, "step": 1}, infotext="Hypertile VAE swap size"),
    }

    for name, opt in options.items():
        opt.section = ('hypertile', "Hypertile")
        shared.opts.add_option(name, opt)


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_before_ui(add_axis_options)

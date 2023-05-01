# Lightener

[![GitHub Release][releases-shield]][releases]
[![hacs][hacsbadge]][hacs]

A Home Assistant integration used to create virtual lights that can be used to control a group of lights with the added benefit of controlling the state (on/off) and the brightness level of each light independently.

## Example use case

Suppose you have the following lights in your living room, all of them available as independent entities in Home Assistant:

 - Main ceiling light
 - Led strip around the ceiling
 - Sofa lamp

 You want to **control all lights at once**, for example having a single switch on the wall to turn all on/off. Easy job, just create a simple automation for that.

Now, you want magic and being able to **control the brightness of the whole room at once**. You don't want to simply having all three lights at the same brightness level (e.g. all at 30%). Instead, you want each light gradually joining the room brightness level. For example:

 - Room brightness 0% to 40%: the ceiling leds gradualy reach 50% of their brightness
 - Room brightness from 20%: sofa light joins in gradually
 - Room brightness 60%: sofa light is at 100% + main light joins in gradually
 - Room brightness 80%: ceiling leds at 100% (sofa still at 100%)
 - Room brightness 100%: main light at 100% (sofa and leds still at 100%)

The above in action:

![Screencast of the example](https://github.com/fredck/lightener/blob/master/images/lightener-example.gif?raw=true "A screencast of the above in action")

This integration allows for the magic to happen.

## Installation

### Using HACS (recommended)

We're applying for [Lightener to be a default reposity in HACS](https://github.com/hacs/default/pull/1821), which will allow for a much simpler installation. Until then, you can install it as a "custom" repository:

 1. Go to HACs in your Home Assistant installation.
 2. Go to "Integrations".
 3. Click the three dots at the top-right of the page and select "Custom repositories".
 4. In "Repository" paste the url of the Lightener GitHub repo: https://github.com/fredck/lightener
 5. In "Category" select "Integration".
 6. Click "Add" and you're all set.

### Manual

Copy the `custom_components/lightener` directory of this repository as `config/custom_components/lightener` in your Home Assistant instalation.

## Configuration

This integration will set up the following platforms.

Platform | Description
-- | --
`lightener` | Virtual lights that manages groups of lights with independent configurable brightness levels.

### Configuration in `configuration.yaml`

The following is a configuration example for the use case above presented:

```yaml
light:
  - platform: lightener
    lights:
      # This defines the entity id of your virtual light ("light.living_room").
      living_room:
        ## The display name of your virtual light (optional).
        friendly_name: "Living Room Lightened"
        ## The list of the existing light entities that will be managed by the virtual light.
        entities:
          light.living_room_ceiling_leds:
            80: 100 # At 80% (room) the leds will reach 100% brightness.
          light.living_room_sofa_light:
            20: 0 # At 20% (room) the sofa light is still off.
            60: 100 # At 60% (room) the sofa light reaches 100% brightness.
          light.living_room_ceiling_light:
            60: 0 # At 60% (room) the main ceiling light is still off.
            # 100: 100 ... no need for this as it is de default.

      # As many virtual lights as you want can be added here.
```

Note that we didn't have to define `40:50` for the leds, as the use case examplifies. That's because the integration will automatically calculate the proper brightness for each step of the room brightness level. Since we configured `80:100`, at 40% (room) the leds will be at 50%, just like they'll be at 25% when the room reaches 20%, etc.

Once Home Assistant is restarted with the above configuration, the `light.living_room` entity will become available and can be used in the UI or in automations to control all the room lights at once.

### Tips

 * A light doesn't have to go always to 100%. If you want it to not cross (e.g.) 80%, just configure it with `100:80`.
 * Brighteness can both raise and decrease. For example `60:100` + `100:20` will make a light be at 100% brightness when the room is at 60% and then decrease its brightnes until 20% when the room is at 100%.
 * A light can go off at any point by setting it to zero. E.g. `30:100` + `60:0` will make it go to 100% when the room is at 30% and gradually go off untill the room reaches 60% (and then back to 100% at 100% because of the following point).
 * Lights will automatically have a `100:100` configuraton so if you need to change it if you want a different behavior.

Have fun!

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge

[releases-shield]: https://img.shields.io/github/release/fredck/lightener.svg?style=for-the-badge
[releases]: https://github.com/fredck/lightener/releases
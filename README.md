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

Simply search for `Lightener` in HACS and install it easily.

### Manual

Copy the `custom_components/lightener` directory of this repository as `config/custom_components/lightener` in your Home Assistant instalation.

## Creating Lightener lights

After planning how you want your lights to work, it is time to create Lightener (virtual) lights that will control them.

To start, in your Home Assistant installation:

  1. Go to "Settings > Devices & Services" to reach the "Integrations" page.
  2. Click the "+ Add Integration" button.
  3. Search/select the "Lightener" integration.

The above will start the configuration flow for a new Lightener light which includes several steps:

  1. Give a name for your Lightener light. This name should make it easy for users to understand which lights are controlled. For example, if several lights in the living room are to be controlled, you may call it "Living Room", simply.
  2. Select the lights that you want to be controlled.
  3. Configure each of the selected lights.

### Light configuration

For every light to be controlled by a Lightener light, you must specify the mapping between the brightness intensity of both the controlling and the controlled lights. This is done by providing a list where every line defines a mapping step.

For example, for the use case previously presented you would have the following configuration (without the parenteshis part):

  * Main ceiling light
    * **60: 0** (At 60% (room) the main ceiling light is still off)
    * (100: 100 ... no need for this as it is de default for 100% (room))
  * Ceiling leds
    * **80: 100** (At 80% (room) the leds will reach 100% brightness)
  * Sofa lamp
    * **20: 0** (At 20% (room) the sofa light is still off)
    * **60: 100** (At 60% (room) the sofa light reaches 100% brightness)

Note that we didn't have to define `40:50` for the leds, as the use case examplifies. That's because the integration will automatically calculate the proper brightness for each step of the room brightness level. Since we configured `80:100`, at 40% (room) the leds will be at 50%, just like they'll be at 25% when the room reaches 20%, etc.

Once the configuration is confirmed a new device becomes available and it can be used in the UI or in automations to control all the room lights at once.

One light to rule them all!

### Tips

 * A light doesn't have to go always to 100%. If you want it to not cross (e.g.) 80%, just configure it with `100:80`.
 * Brighteness can both raise and decrease. For example `60:100` + `100:20` will make a light be at 100% brightness when the room is at 60% and then decrease its brightnes until 20% when the room is at 100%.
 * A light can go off at any point by setting it to zero. E.g. `30:100` + `60:0` will make it go to 100% when the room is at 30% and gradually go off untill the room reaches 60% (and then back to 100% at 100% because of the following point).
 * Lights will automatically have a `100:100` configuraton so if you need to change the 100% default if you want a different behavior.

Have fun!

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge

[releases-shield]: https://img.shields.io/github/release/fredck/lightener.svg?style=for-the-badge
[releases]: https://github.com/fredck/lightener/releases
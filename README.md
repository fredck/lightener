# Lightener

[![GitHub Release][releases-shield]][releases]
[![hacs][hacsbadge]][hacs]

Lightener is a Home Assistant integration used to create virtual lights that can control a group of lights. It offers the added benefit of controlling the state (on/off) and brightness level of each light independently.

## Example Use Case

Suppose you have the following lights in your living room, all available as independent entities in Home Assistant:

- Main ceiling light
- LED strip around the ceiling
- Sofa lamp

You want to **control all lights at once**, such as having a single switch on the wall to turn all lights on/off. It's an easy task, simply create a simple automation for that.

Now, you want something magical: the ability to **control the brightness of the whole room at once**. You don't want all three lights to have the same brightness level (e.g., all at 30%). Instead, you want each light to gradually match the room's brightness level. For example:

- Room brightness 0% to 40%: the ceiling LEDs gradually reach 50% of their brightness.
- Room brightness from 20%: the sofa light gradually joins in.
- Room brightness 60%: the sofa light is at 100%, and the main light joins in gradually.
- Room brightness 80%: the ceiling LEDs are at 100% (sofa light remains at 100%).
- Room brightness 100%: the main light is at 100% (sofa light and LEDs still at 100%).

Here's a screencast demonstrating the above in action:

![Screencast of the example](https://github.com/fredck/lightener/blob/master/images/lightener-example.gif?raw=true "A screencast of the above in action")

Lightener makes this magic possible.

## Installation

### Using HACS (recommended)

Simply search for `Lightener` in HACS and easily install it.

### Manual

Copy the `custom_components/lightener` directory from this repository to `config/custom_components/lightener` in your Home Assistant installation.

## Creating Lightener Lights

After planning how you want your lights to work, it's time to create Lightener (virtual) lights that will control them.

To start, follow these steps in your Home Assistant installation:

1. Go to "Settings > Devices & Services" to access the "Integrations" page.
2. Click the "+ Add Integration" button.
3. Search for and select the "Lightener" integration.

This will initiate the configuration flow for a new Lightener light, which includes several steps:

1. Give a name to your Lightener light. The name should make it easy for users to understand which lights are being controlled. For example, if you want to control several lights in the living room, you can name it "Living Room".
2. Select the lights that you want to control.
3. Configure each of the selected lights.

### Light Configuration

For each light to be controlled by a Lightener light, you must specify the mapping between the brightness intensity of both the controlling and the controlled lights. This is done by providing a list where each line defines a mapping step.

For example, in the previously presented use case, the configuration would be as follows (without the parentheses):

- Main ceiling light
  - **60: 0** (At 60% room brightness, the main ceiling light is still off)
  - (100: 100 ... no need for this as it is the default for 100% room brightness)
- Ceiling LEDs
  - **80: 100** (At 80% room brightness, the LEDs will reach 100% brightness)
- Sofa lamp
  - **20: 0** (At 20% room brightness, the sofa light is still off)
  - **60: 100** (At 60% room brightness, the sofa light reaches 100% brightness)

Note that we didn't have to define `40:50` for the LEDs, as the use case exemplifies. This is because the integration will automatically calculate the proper brightness for each step of the room brightness level. Since we configured `80:100`, at 40% room brightness, the LEDs will be at 50%, just like they'll be at 25% when the room reaches 20%, and so on.

Once the configuration is confirmed, a new device becomes available, which can be used in the UI or in automations to control all the lights in the room at once.

One light to rule them all!

### Support for On/Off Lights

Lightener supports controlling so-called "On/Off Lights." These are lights that cannot be dimmed but can only be turned on and off.

The configuration of On/Off Lights is similar to dimmable lights. The difference is that if the light is set to zero, it will be off. Any other "brightness" level will simply turn the light on.

For example, if an On/Off Light is configured with "20:0, 50:30, 100:0," it will be set to off when the Lightener is in the brightness range of 0-20% or when it reaches 100%. Between 21-99%, the light will be on.

### Tips

- A light doesn't have to always go to 100%. If you don't want it to exceed, for example, 80%, you can configure it with `100:80`.
- Brightness can both increase and decrease. For example, `60:100` + `100:20` will make a light be at 100% brightness when the room is at 60%, and then decrease its brightness until 20% when the room is at 100%.
- A light can be turned off at any point by setting it to zero. For example, `30:100` + `60:0` will make it go to 100% when the room is at 30% and gradually turn off until the room reaches 60% (and then back to 100% at 100% because of the following point).
- Lights will automatically have a `100:100` configuration, so if you need to change the default behavior at 100%, you can adjust it accordingly.

Have fun!

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge

[releases-shield]: https://img.shields.io/github/release/fredck/lightener.svg?style=for-the-badge
[releases]: https://github.com/fredck/lightener/releases

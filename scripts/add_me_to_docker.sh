#!/bin/bash
sudo usermod -aG docker $USER
echo "Please reboot for user group changes to take effect"
read -n 1 -p "Reboot now? [y/n]" -s && echo
if [[ "$REPLY" == "y" ]]
    then sudo reboot
fi
# DigitalOcean Meta-Write

dometawrite is a tool that helps system administrators take information from the DigitalOcean API and/or Dropleta Metadata API
to create text files such as configuration files, status pages or anything else that can be coded in a template.

Templates are written using the most-excellent Jinja2 library for Python.

# Example: Create SSH client configuration

dometawrite can be used to create an OpenSSH SSH Client configuration file that can be included from ~/.ssh/config for 
easy access to your droplets. Picture this:

    ~ $ dometawrite --template ssh-config  \
                    --api-key $DO_API_KEY  \
                    --output /home/example/.ssh/digitalocean_droplets \
                    --template-var=user:root --template-var=keyfile:/home/example/id_rsa_digitalocean

The above command will render the ssh-config dometawrite template, and write the output to the /home/example/.ssh/digitalocean_droplets file.

It will use the indicated DigitalOcean API KEY, and will also provide some additional variables to the template. If any variables
are missing from the command line, dometawrite will let you know.

The resulting output may look like this:

    Host droplet-name
    HostName droplet_ip_address
    User root
    IdentityFile /home/example/id_rsa_digitalocean
    
    Host another_droplet
    HostName yet_another_ip
    User root
    IdentityFile /home/example/id_rsa_digitalocean

As long as the id_rsa_digitalocean.pub file has been added to the droplet, either during creation or afterwards, then you will be able to
simply:

    ssh root@another_droplet

# Example: Create ansible inventory

Maybe you use ansible, and you want to update your hosts inventory dynamically:

    dometawrite --template ansible-inventory \
                --api-key $DO_API_KEY        \
                --output /etc/ansible/hosts/digitaloceaninventory

The template will receive a python dictionary with all necessary information. Jinja2 supports advanced logic, so it can easily contain
all the required code to output a valid Ansible Inventory file.

# Templating Ideas

Templates will have to indicate endpoint requirements. For example, for the ssh-config template:

    {% set required_endpoints = ['/v2/droplets'] %}
    {% for droplet in droplets.droplets %}
    Host {{ droplet.name }}
    etcetc

    {% endfor %}


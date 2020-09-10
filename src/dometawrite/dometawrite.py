import os
import sys
import json
import requests
import argparse
from jinja2 import (Environment,
                    FileSystemLoader,
                    contextfunction as jinja2ctxfunc)
from pprint import pprint

__version__ = '0.1.14'


@jinja2ctxfunc
def get_context(c):
    return(c)


def printerr(msg):
    print("{}".format(msg), file=sys.stderr)


def pprinterr(o):
    pprint(o, stream=sys.stderr)


def envOrDefault(v, d):
    # return the contents of an env var 'v'
    # or default d.
    ov = os.environ.get(v)
    if ov is None:
        return(d)
    else:
        return(str(ov).strip())


class DOMetaWrite():
    def __init__(self,
                 template=None,
                 output_file=None,
                 user_vars=None,
                 api_key=None,
                 debug=False):
        self._RESERVED_TPL_VARS = ['endpoint_requirements',
                                   'userdata_requirements']
        self.apiUrlBase = 'https://api.digitalocean.com/v2/'
        self.dropletApiUrl = 'http://169.254.169.254/metadata/v1.json'
        self.debug = debug
        self.output_file = output_file
        self.user_vars = self.dictify_user_vars(user_vars)
        if template is None:
            raise(ValueError('DOMetaWrite: template cannot be None'))
        else:
            if not template.endswith('.jinja'):  # FIX: horrible
                template = '{}.jinja'.format(template)
            self.template = template

        self.tplPath = os.path.join(os.path.dirname(__file__), './templates')
        if self.debug:
            print('self.tplPaht={}'.format(self.tplPath))

        # TODO: replace with FunctionLoader for more flexibility
        self.loader = FileSystemLoader(searchpath=self.tplPath)
        self.jinja2 = Environment(loader=self.loader, trim_blocks=True)

        self.setup_template_data()

        self.tpl_reqs = self.get_template_requirements()
        # If the only endpoint requirement is 'metadata'
        # no api_key is required
        if api_key is None and not self.metadata_only():
            printerr('DOMetaWrite: You need to specify DO API KEY.')
            sys.exit(1)
        else:
            self.api_key = api_key
        if self.debug:
            printerr(self.tpl_reqs)

    def metadata_only(self):
        if self.tpl_reqs['endpoint'] == ['metadata']:
            return(True)
        return(False)

    def get_missing_user_vars(self):
        retObj = []
        if 'userdata' in self.tpl_reqs.keys():
            for var in self.tpl_reqs['userdata']:
                if var not in self.user_vars:
                    retObj.append(var)
        return(retObj)

    def execute_api_calls(self):
        retObj = {}
        for endpoint in self.tpl_reqs['endpoint']:
            if self.debug:
                printerr('About to call endpoint={}'.format(endpoint))
            ed = self.get_api_dictionary(endpoint=endpoint)
            retObj[endpoint.replace('/', '_')] = ed
            if self.debug:
                pprinterr(ed)
        self.apiData = retObj
        return(self.apiData)

    def setup_template_data(self):
        if self.debug:
            print('self.template={}'.format(self.template))
        self.template_source = self.loader.get_source(self.jinja2,
                                                      self.template)[0]
        self.parsed_content = self.jinja2.parse(self.template_source)

    def get_template_requirements(self):
        retObj = {}
        for i in range(len(self.parsed_content.body)):
            if not hasattr(self.parsed_content.body[i], 'target'):
                continue
            target = self.parsed_content.body[i].target
            if not hasattr(target, 'name'):
                continue
            target_name = target.name
            if target_name in self._RESERVED_TPL_VARS:
                nodeitems = self.parsed_content.body[i].node.items
                target_values = [a.value for a in nodeitems]
                sName = target_name.split('_')[0]
                retObj[sName] = target_values
                if self.debug:
                    printerr(target_name)
                    pprinterr(target_values)
        return(retObj)

    def get_api_dictionary(self, endpoint=None):
        if endpoint is None:
            raise(ValueError('get_api_dictionary: endpoint cant be None'))

        if endpoint == 'metadata':
            # No need for api key nor headers. shorter timeout.
            api = self.dropletApiUrl
            headers = {}
            timeout = 5
        else:
            api = '{}{}'.format(self.apiUrlBase, endpoint)
            headers = {'Authorization': 'Bearer {}'.format(self.api_key)}
            timeout = 30
        try:
            r = requests.get(api, headers=headers, timeout=timeout)
        except Exception as exc:
            printerr('DOMetaWrite: Error for https request endpoint={}'
                     .format(endpoint))
            if endpoint == 'metadata':
                printerr('DOMetaWrite: Metadata only works on Droplets')
            printerr(exc)
            sys.exit(3)
        return(r.json())

    def dictify_user_vars(self, user_vars):
        if user_vars is None:
            return({})
        d = {}
        for item in user_vars:
            for c in [':', '=']:  # Yeah, I know...
                if item.count(c) == 1:
                    splitChar = c
            (var, val) = item.split(splitChar)
            d[var] = val
        return(d)

    def render(self):
        jvars = self.apiData
        userdata = {'userdata': self.user_vars}
        jvars.update(userdata)
        template = self.template
        # Render
        try:
            t = self.jinja2.get_template(self.template)
            t.globals['context'] = get_context
            t.globals['callable'] = callable
            r = t.render(jvars)
        except Exception as exc:
            print('DOMetaWrite: Rendering Exception:')
            print(exc)
            sys.exit(2)
        if self.debug:
            print(r)
        if self.output_file is None:  # write to stdout
            print(r)
        else:  # try to write to file
            with open(self.output_file, 'w') as o:
                o.write(r)
                o.close()
        return(r)


def run():
    parser = argparse.ArgumentParser(description='''Tool that creates
output from jinja templates using information from the DigitalOcean APIv2
and Droplet Metadata API, including user-supplied variables.

It can be used to create OpenSSH Host configuration files, Ansible
Host inventories, informational dashboards, etc.''')
    parser.add_argument('-a', '--api-key',
                        default=envOrDefault('DIGITALOCEAN_ACCESS_TOKEN',
                                             None),
                        dest='api_key',
                        metavar='APIKEY',
                        help='''Specify DigitalOcean API Key with read
scope. If missing dometawrite will attempt to retrieve it from the
DIGITALOCEAN_ACCESS_TOKEN environment variable, or fail.''')
    parser.add_argument('-t', '--template',
                        default=None,
                        dest='template',
                        metavar='TEMPLATE_NAME',
                        help='''Template to use. Ex: ssh-config or
/path/to/template.jinja''')
    parser.add_argument('-o', '--output-file',
                        default=None,
                        dest='output_file',
                        metavar='FILE',
                        help='''Write result to indicated FILE. If not
indicated, write to stdout.''')
    parser.add_argument('-u', '--user-var',
                        action='append',
                        dest='user_vars',
                        metavar='VAR=VALUE or VAR:VALUE',
                        help='''User variables to pass to the template. Any
missing variable will be reported prior to stopping execution.''')
    parser.add_argument('--debug',
                        action='store_true',
                        dest='debug',
                        help='Enable debugging messages.')

    args = parser.parse_args()

    if args.template is None:
        printerr('DOMetaWrite: You must indicate desired template using -t.')
        parser.print_help()
        sys.exit(1)

    domw = DOMetaWrite(template=args.template,
                       output_file=args.output_file,
                       user_vars=args.user_vars,
                       api_key=args.api_key,
                       debug=args.debug)
    muv = domw.get_missing_user_vars()
    if len(muv) > 0:
        printerr('Missing user vars. Use -u var=value! {}'.format(muv))
        sys.exit(1)
    domw.execute_api_calls()
    domw.render()


if __name__ == '__main__':
    run()

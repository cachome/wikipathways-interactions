import argparse
import glob
import os
import re
import ssl
from time import sleep

import requests
from lxml import etree

# # Enable importing local modules when directly calling as script
# if __name__ == "__main__":
#     cur_dir = os.path.join(os.path.dirname(__file__))
#     sys.path.append(cur_dir + "/..")

# from lib import download_gzip

repo = "cachome/wikipathways-interactions"
module = "interactions.py"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Organisms configured for WikiPathways caching
organisms = [
    "Homo sapiens",
    # "Mus musculus"
    ## "Danio rerio",
    ## "Gallus gallus",
    ## "Rattus norvegicus",
    ## "Pan troglodytes",
    ## "Canis lupus familiaris",
    ## "Equus caballus",
    ## "Bos taurus",
    ## "Caenorhabditis elegans"
]

def get_gpml_zip_url(organism):
    date = "20220110"
    base = f"https://wikipathways-data.wmcloud.org/{date}/gpml/"
    org_us = organism.replace(" ", "_")
    url = f"{base}wikipathways-{date}-gpml-{org_us}.zip"
    return url

def unwrap_leaf(tree, has_bloat, leaf=None, selector=None):
    """Helper for `unwrap` function
    """
    ns_map = {"gpml": "http://pathvisio.org/GPML/2013a"}
    if not selector:
        selector = f"//gpml:g[{has_bloat}]/gpml:g[{has_bloat}]/gpml:" + leaf
    elements = tree.xpath(selector, namespaces=ns_map)
    for element in elements:
        parent = element.getparent()
        grandparent = parent.getparent()
        grandparent.replace(parent, element)

def get_has_class_clause(raw_class):
    """Enable typical class selectors in XPath, akin to CSS ".foo"

    XPath makes it complicated to detect if a string is among class values.
    That functionality is typical for class selectors, so tailor syntax to
    ease such common queries.
    """
    normed_class = "concat(' ', normalize-space(@class), ' ')"
    has_class_clause = 'contains(' + normed_class + ', "' + raw_class + '")'
    return has_class_clause

def condense_colors(xml):
    """Condense colors by using hexadecimal abbreviations where possible.
    Consider using an abstract, general approach instead of hard-coding.
    """
    xml = re.sub('000000', '000', xml)
    xml = re.sub('ff0000', 'f00', xml)
    xml = re.sub('00ff00', '0f0', xml)
    xml = re.sub('0000ff', '00f', xml)
    xml = re.sub('00ffff', '0ff', xml)
    xml = re.sub('ff00ff', 'f0f', xml)
    xml = re.sub('ffff00', 'ff0', xml)
    xml = re.sub('ffffff', 'fff', xml)
    xml = re.sub('cc0000', 'c00', xml)
    xml = re.sub('00cc00', '0c0', xml)
    xml = re.sub('0000cc', '00c', xml)
    xml = re.sub('00cccc', '0cc', xml)
    xml = re.sub('cc00cc', 'c0c', xml)
    xml = re.sub('cccc00', 'cc0', xml)
    xml = re.sub('cccccc', 'ccc', xml)
    xml = re.sub('999999', '999', xml)
    xml = re.sub('808080', 'grey', xml)

    return xml

def lossy_optimize_gpml(gpml, pwid):
    """Lossily decrease size of WikiPathways GPML
    """
    ns_map = {
        "gpml": "http://pathvisio.org/GPML/2013a",
        "bp": "http://www.biopax.org/release/biopax-level3.owl#"
    }

    gpml = re.sub(pwid.lower(), '', gpml)

    gpml = gpml.replace('<?xml version="1.0" encoding="UTF-8"?>\n', '')

    # print('gpml')
    # print(gpml)

    tree = etree.fromstring(gpml)

    positional_attrs = [
        "X", "Y", "CenterX", "CenterY", "Valign", "RelX", "RelY", "Rotation",
        "Position"
    ]
    extraneous_attrs = positional_attrs + [
        "ZOrder", "FontWeight", "FontSize", "LineThickness",
        "Width", "Height" # These two might be useful later, but not now
    ]
    # print('tree')
    # print(tree)
    # print('pwid')
    # print(pwid)
    elements = tree.xpath('//*')
    for el in elements:
        for attr_name in extraneous_attrs:
            if attr_name in el.attrib: del el.attrib[attr_name]

    extraneous_elements = ["Attribute", "Xref", "Label"]
    # key = '@Key="org.pathvisio.model.BackpageHead"'
    # selector = f"//gpml:Attribute[{key}]"
    for el_name in extraneous_elements:
        selector = f"//gpml:{el_name}"
        attribute_elements = tree.xpath(selector, namespaces=ns_map)
        for el in attribute_elements:
            el.getparent().remove(el)

    # controls = tree.xpath('//*[@class="gpml-pan-zoom-control"]')[0]
    # tree.remove(controls)
    # controls_style = tree.xpath('//*[@id="gpml-pan-zoom-controls-styles"]')[0]
    # controls_style.getparent().remove(controls_style)

    try:
        xml = etree.tostring(tree).decode("utf-8")
    except Exception as e:
        msg = f"Encountered error converting XML for pathway {pwid}"
        raise Exception(msg)

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml

    rdf_datatype = 'rdf:datatype="http://www.w3.org/2001/XMLSchema#string"'
    xml = re.sub(rdf_datatype, '', xml)

    xml = re.sub('<Xref Database="" ID="" />', '', xml)

    xml = re.sub('<Graphics/>\n', '', xml)

    xml = re.sub('<Point/>\n', '', xml)

    xml = re.sub('Shape="None" ', '', xml)

    xml = condense_colors(xml)

    # xml = re.sub('xml:space="preserve"', '', xml)

    # # Remove "px" from attributes where numbers are assumed to be pixels.
    # xml = re.sub(r'width="([0-9.]+)px"', r'width="\1"', xml)

    # xml = re.sub('fill="inherit"', '', xml)

    # # Match any anchor or group tag, up until closing angle bracket (>), that
    # # includes a color attribute with the value black (#000).
    # # For such matches, remove the color attribute but not anything else.
    # xml = re.sub(r'<g([^>]*)(color="#000")', r'<g \1', xml)

    # xml = re.sub(r'<(rect class="Icon"[^>]*)(color="#000")', r'<rect \1', xml)

    # xml = re.sub(r'<(text class="Text"[^>]*)(fill="#000")', r'<\1', xml)
    # xml = re.sub(r'<(text class="Text"[^>]*)(stroke="white" stroke-width="0")', r'<\1', xml)

    # xml = re.sub(r'class="([^"]*)( Node)"', r'class="\1"', xml)

    # xml = re.sub(r'id="[^"]*-text-clipPath"', '', xml)

    # # Remove class attributes from elements where it can be deduced
    # xml = re.sub(r'<rect([^>]*)(class="[^"]*)"', r'<rect \1', xml)

    # xml = re.sub(r'<path([^>]*)(id="[^"]*)"', r'<path \1', xml)
    # # xml = re.sub(r'<path([^>]*)(fill="transparent")', r'<path \1', xml)

    # xml = re.sub(r'id="[^"]*-icon" ', '', xml)
    # xml = re.sub(r'id="[^"]*-text" class="[^"]*"', '', xml)

    # # Round any floats to 2 decimal places
    # xml = re.sub(r'\d*\.\d{2,}', lambda m: format(float(m.group(0)), '.2f'), xml)

    # # Remove extraneous spaces
    # xml = re.sub(r'\s{2,}', ' ', xml)

    return xml

class WikiPathwaysCache():

    def __init__(self, output_dir="data/", reuse=False):
        self.output_dir = output_dir
        self.tmp_dir = f"tmp/"
        self.reuse = reuse

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def fetch_gpml(self, ids_and_names, org_dir):

        prev_error_pwids = []
        error_pwids = []

        error_path = org_dir + "error_pwids.csv"
        if os.path.exists(error_path):
            with open(error_path) as f:
                prev_error_pwids = f.read().split(",")
                error_pwids = prev_error_pwids

        for i_n in ids_and_names:
            id = i_n[0]
            gpml_path = org_dir + id + ".gpml"

            if self.reuse:
                if os.path.exists(gpml_path):
                    print(f"Found cache; skip processing {id}")
                    continue
                elif id in prev_error_pwids:
                    print(f"Found previous error; skip processing {id}")
                    continue

            # url = f"https://www.wikipathways.org/index.php/Pathway:{id}?view=widget"

            # try:
            #     sleep(1)
            #     selector = "svg.Diagram"
            #     raw_content = self.driver.find_element_by_css_selector(selector)
            #     content = raw_content.get_attribute("outerHTML")
            # except Exception as e:
            #     print(f"Encountered error when stringifying GPML for {id}")
            #     error_pwids.append(id)
            #     with open(error_path, "w") as f:
            #         f.write(",".join(error_pwids))
            #     sleep(0.5)
            #     continue

            gpml = content.replace(
                'typeof="Diagram" xmlns:xlink="http://www.w3.org/1999/xlink"',
                'typeof="Diagram"'
            )

            print("Preparing and writing " + gpml_path)

            gpml = '<?xml version="1.0" encoding="UTF-8"?>\n' + gpml

            with open(gpml_path, "w") as f:
                f.write(gpml)
            sleep(1)

    def optimize_gpml(self, org_dir):

        optimize_error_pwids = []

        for gpml_path in glob.glob(f'{org_dir}*.gpml'):
        # for gpml_path in ["tmp/homo-sapiens/WP231.gpml"]: # debug

            # print('gpml')
            # print(gpml)
            original_name = gpml_path.split("/")[-1]
            name = original_name.split(".gpml")[0]
            pwid = re.search(r"WP\d+", name).group() # pathway ID
            optimized_xml_path = self.output_dir + pwid + ".xml"
            print(f"Optimizing to create: {optimized_xml_path}")

            # try:
            #     gpml_xml = scour.scourString(gpml, options=scour_options)
            # except Exception as e:
            #     print(f"Encountered error while optimizing GPML for {pwid}")
            #     continue

            repo_url = f"https://github.com/{repo}/tree/main/"
            code_url = f"{repo_url}src/{module}"
            data_url = f"{repo_url}{optimized_xml_path}"
            wp_url = f"https://www.wikipathways.org/index.php/Pathway:{pwid}"
            provenance = "\n".join([
                "<!--",
                f"  WikiPathways page: {wp_url}",
                f"  URL for this compressed file: {data_url}",
                # f"  Uncompressed GPML file: {original_name}",
                # f"  From upstream ZIP archive: {url}",
                f"  Source code for compression: {code_url}",
                "-->"
            ])

            with open(gpml_path, 'r') as f:
                gpml = f.read()

            try:
                xml = lossy_optimize_gpml(gpml, pwid)
            except Exception as e:
                handled = "Encountered error converting XML for pathway"
                if handled in str(e):
                    # print('Handled an error')
                    print(e)
                    optimize_error_pwids.append(pwid)
                    continue
                else:
                    print('Encountered fatal error')
                    print(e)
                    raise Exception(e)

            with open(optimized_xml_path, "w") as f:
                f.write(xml)

        num_errors = len(optimize_error_pwids)
        if num_errors > 0:
            print(f"{num_errors} pathways had optimization errors:")
            print(",".join(optimize_error_pwids))

    def populate_by_org(self, organism):
        """Fill caches for a configured organism
        """
        org_dir = self.tmp_dir + organism.lower().replace(" ", "-") + "/"
        if not os.path.exists(org_dir):
            os.makedirs(org_dir)

        # self.fetch_gpml(ids_and_names, org_dir)
        self.optimize_gpml(org_dir)

    def populate(self):
        """Fill caches for all configured organisms

        Consider parallelizing this.
        """
        for organism in organisms:
            self.populate_by_org(organism)

# Command-line handler
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory to put outcome data.  (default: %(default))"
        ),
        default="data/"
    )
    parser.add_argument(
        "--reuse",
        help=(
            "Whether to use previously-downloaded raw GPML zip archives"
        ),
        action="store_true"
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    reuse = args.reuse

    WikiPathwaysCache(output_dir, reuse).populate()

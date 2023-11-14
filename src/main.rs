use base64::Engine as _;
use reqwest::{blocking::Client, header::REFERER};
use scraper::{Html, Selector};

const OUTPUT_DIR: &str = "output";
const BASE_URL: &str = "https://aip.dfs.de/BasicVFR/2023OCT20/chapter";
const PRINT_URL: &str = "https://aip.dfs.de/basicVFR/print/AD";

struct Link {
    href: String,
    name: String,
}

fn get_html(path: &str) -> String {
    let res = reqwest::blocking::get(format!("{BASE_URL}/{path}")).unwrap();

    let body = res.text().unwrap();
    body
}

fn get_hrefs(html: &str, anchor_selector: &Selector, title_selector: &Selector) -> Vec<Link> {
    let document = Html::parse_document(html);

    document
        .select(anchor_selector)
        .filter_map(|element| {
            Some(Link {
                name: element.select(title_selector).next().unwrap().inner_html(),
                href: element.value().attr("href").unwrap().to_string(),
            })
        })
        .collect()
}

fn get_base64_chart(client: &Client, link: &Link) -> String {
    let url = get_print_link(link);
    let res = client
        .get(url.as_str())
        .header(REFERER, url.as_str())
        .send()
        .expect("Request failed");
    let selector = scraper::Selector::parse(".d-print-block img").expect("Error in the selector");
    let document = scraper::Html::parse_document(res.text().unwrap().as_str());
    let img = document.select(&selector).next().expect("Image not found");
    img.value()
        .attr("src")
        .expect("No src")
        .replace("data:image/png;base64,", "")
}

fn save_base64_to_png(input: &str, output: &str) {
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(input)
        .expect("Failed to decode Base64 string");

    let image = image::load_from_memory(&decoded).unwrap();

    let mut output_file = std::fs::File::create(format!("{OUTPUT_DIR}/{}", output))
        .expect("Failed to create output file");
    image
        .write_to(&mut output_file, image::ImageOutputFormat::Png)
        .expect("Failed to write image to file");
    println!("Image saved to {}", output);
}

fn get_print_link(link: &Link) -> String {
    format!(
        "{PRINT_URL}/{}/{}",
        link.href.replace("../pages/", "").replace(".html", ""),
        link.name
    )
}

fn download_airfield_docs(client: &Client, href: &str) {
    let document_link_selector = Selector::parse("a.document-link[href]").unwrap();
    let document_title_selector = Selector::parse("span.document-name[lang='en']").unwrap();

    let airfield_html = get_html(href);
    let document_hrefs = get_hrefs(
        airfield_html.as_str(),
        &document_link_selector,
        &document_title_selector,
    );

    for doc in &document_hrefs {
        let chart = get_base64_chart(&client, doc);
        save_base64_to_png(
            chart.as_str(),
            format!("{}.png", doc.name.as_str()).as_str(),
        );
    }
}

fn main() {
    let client = Client::new();

    let _ = std::fs::create_dir(OUTPUT_DIR);

    let folder_link_selector = Selector::parse("a.folder-link[href]").unwrap();
    let folder_name_selector = Selector::parse("span.folder-name[lang='en']").unwrap();

    let index_page = get_html("3f88a2e1b3232c9cec4ac3420a303de0.html");
    let chapter_pages = get_hrefs(
        index_page.as_str(),
        &folder_link_selector,
        &folder_name_selector,
    );

    for page in &chapter_pages[3..] {
        println!("\n{}", page.name);
        let chapter_html = get_html(page.href.as_str());

        let airfield_pages = get_hrefs(
            chapter_html.as_str(),
            &folder_link_selector,
            &folder_name_selector,
        );

        for airfield_page in &airfield_pages {
            println!("Airfield: {}", airfield_page.name);
            download_airfield_docs(&client, airfield_page.href.as_str());
        }
    }
}

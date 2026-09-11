# Fetchuccini hotfix v0.5

## MagicDealers images

MagicDealers (CrystalCommerce) already exposes each product image in the search-result HTML.
The previous adapter parsed price, stock, condition and language from that page but never copied
the image URL into the normalized `Listing`, so the frontend had nothing to render.

v0.5 now:
- extracts the product image from the exact product link in the search HTML;
- normalizes relative image URLs;
- preserves the image even if the optional detail-page request fails or returns 503;
- passes `image_url` through both the normal and fallback MagicDealers listing paths.

#!/usr/bin/env python3
"""One-shot seed: 50 Cute Things demo products with details + images.

Human-named live write. Tags all rows with demo-seed-2026-09.
Uses Admin GraphQL 2026-07: productCreate + media, productVariantsBulkUpdate,
publishablePublish (Online Store).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "console-src" / "helpdesk-agent"))

from helpdesk.auth import mint_token, require_pinned_shop  # noqa: E402
from helpdesk.env import load_shopify_env  # noqa: E402

SEED_TAG = "demo-seed-2026-09"
ONLINE_STORE_PUBLICATION = "gid://shopify/Publication/203073847469"
VENDOR = "Cute Things"

# Curated Unsplash stills (baby / nursery / soft goods). Shopify fetches originalSource.
PRODUCTS: list[dict] = [
    {
        "title": "Linen Nursery Storage Bin",
        "type": "Nursery",
        "price": "28.00",
        "sku": "CT-SEED-01-LINEN-BIN",
        "desc": "Collapsible linen bin for diapers, wipes, and soft toys. Removable cotton liner.",
        "tags": ["nursery", "storage", "linen"],
        "img": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=900&h=900&fit=crop&q=80",
        "alt": "Linen storage bin in a nursery",
    },
    {
        "title": "Organic Cotton Footed Pajamas",
        "type": "Baby apparel",
        "price": "36.00",
        "sku": "CT-SEED-02-FOOTED-PJ",
        "desc": "GOTS organic cotton footie with fold-over mittens and two-way zipper.",
        "tags": ["apparel", "sleep", "organic"],
        "img": "https://images.unsplash.com/photo-1522771930-78848d929f64?w=900&h=900&fit=crop&q=80",
        "alt": "Baby in soft cotton pajamas",
    },
    {
        "title": "Muslin Swaddle Trio",
        "type": "Swaddles",
        "price": "42.00",
        "sku": "CT-SEED-03-MUSLIN-TRIO",
        "desc": "Three breathable cotton muslin swaddles in soft neutrals. Machine washable.",
        "tags": ["swaddle", "muslin", "gift"],
        "img": "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=900&h=900&fit=crop&q=80",
        "alt": "Folded muslin baby swaddles",
    },
    {
        "title": "Silicone Feeding Bowl Set",
        "type": "Feeding",
        "price": "24.00",
        "sku": "CT-SEED-04-SILICONE-BOWL",
        "desc": "Suction-base silicone bowl with matching spoon. BPA-free, dishwasher safe.",
        "tags": ["feeding", "silicone", "mealtime"],
        "img": "https://images.unsplash.com/photo-1604881991720-f91add269bed?w=900&h=900&fit=crop&q=80",
        "alt": "Baby feeding bowl and spoon",
    },
    {
        "title": "Wooden Stacking Rings",
        "type": "Toys",
        "price": "22.00",
        "sku": "CT-SEED-05-STACK-RINGS",
        "desc": "Beechwood stacking rings finished with plant-based wax. Ages 6 months+.",
        "tags": ["toys", "wood", "montessori"],
        "img": "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=900&h=900&fit=crop&q=80&sat=-20",
        "alt": "Wooden stacking toy for babies",
    },
    {
        "title": "Quilted Changing Pad Cover",
        "type": "Nursery",
        "price": "32.00",
        "sku": "CT-SEED-06-CHANGE-COVER",
        "desc": "Fitted quilted cover with waterproof backing. Soft cotton face, elastic edges.",
        "tags": ["nursery", "changing", "cotton"],
        "img": "https://images.unsplash.com/photo-1587654780291-39c9404d746b?w=900&h=900&fit=crop&q=80",
        "alt": "Quilted nursery changing pad",
    },
    {
        "title": "Merino Wool Baby Bonnet",
        "type": "Baby apparel",
        "price": "29.00",
        "sku": "CT-SEED-07-WOOL-BONNET",
        "desc": "Soft merino knits that regulate temperature. Tie under the chin.",
        "tags": ["apparel", "wool", "accessories"],
        "img": "https://images.unsplash.com/photo-1544126592-807ade215a0b?w=900&h=900&fit=crop&q=80",
        "alt": "Knitted baby bonnet",
    },
    {
        "title": "Cotton Gauze Dream Blanket",
        "type": "Blankets",
        "price": "48.00",
        "sku": "CT-SEED-08-GAUZE-BLANKET",
        "desc": "Four-layer cotton gauze blanket with stitched edge. Light for year-round use.",
        "tags": ["blankets", "gauze", "gift"],
        "img": "https://images.unsplash.com/photo-1555252333-9f8e92e65df9?w=900&h=900&fit=crop&q=80",
        "alt": "Soft baby blanket folded",
    },
    {
        "title": "Bamboo Nightgown Set",
        "type": "Baby apparel",
        "price": "34.00",
        "sku": "CT-SEED-09-BAMBOO-NIGHT",
        "desc": "Two bamboo-viscose nightgowns with envelope neck. Cool and stretchy.",
        "tags": ["apparel", "sleep", "bamboo"],
        "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba?w=900&h=900&fit=crop&q=80",
        "alt": "Baby sleepwear on soft bedding",
    },
    {
        "title": "Ceramic Night Light Lamp",
        "type": "Nursery",
        "price": "54.00",
        "sku": "CT-SEED-10-NIGHT-LAMP",
        "desc": "Warm-glow ceramic lamp with dimmer. Nursery-safe LED, no hot surfaces.",
        "tags": ["nursery", "lighting", "sleep"],
        "img": "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?w=900&h=900&fit=crop&q=80",
        "alt": "Warm ceramic night lamp",
    },
    {
        "title": "Organic Cotton Snap Bodysuit 3-Pack",
        "type": "Baby apparel",
        "price": "39.00",
        "sku": "CT-SEED-11-BODYSUIT-3",
        "desc": "Three everyday snap bodysuits in cream, oat, and sage. Envelope shoulders.",
        "tags": ["apparel", "basics", "organic"],
        "img": "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=900&h=900&fit=crop&q=80",
        "alt": "Stack of cotton baby bodysuits",
    },
    {
        "title": "Felt Animal Mobile",
        "type": "Nursery",
        "price": "58.00",
        "sku": "CT-SEED-12-FELT-MOBILE",
        "desc": "Hand-felted woodland animals on a beech hanger. For display above the crib.",
        "tags": ["nursery", "mobile", "felt"],
        "img": "https://images.unsplash.com/photo-1566454825481-9c31f4b4a5f1?w=900&h=900&fit=crop&q=80",
        "alt": "Felt animal crib mobile",
    },
    {
        "title": "Silicone Teething Beads",
        "type": "Baby gift",
        "price": "16.00",
        "sku": "CT-SEED-13-TEETH-BEADS",
        "desc": "Food-grade silicone teething beads on a short cord. Freezer-friendly.",
        "tags": ["teething", "gift", "silicone"],
        "img": "https://images.unsplash.com/photo-1596461404969-9ae70f2167ec?w=900&h=900&fit=crop&q=80",
        "alt": "Silicone baby teething beads",
    },
    {
        "title": "Linen Sun Hat",
        "type": "Baby apparel",
        "price": "26.00",
        "sku": "CT-SEED-14-LINEN-HAT",
        "desc": "Wide-brim linen hat with soft chin ties. Packs flat for stroller days.",
        "tags": ["apparel", "sun", "linen"],
        "img": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?w=900&h=900&fit=crop&q=80",
        "alt": "Baby wearing a linen sun hat",
    },
    {
        "title": "Cotton Play Mat Quilt",
        "type": "Gear",
        "price": "72.00",
        "sku": "CT-SEED-15-PLAY-MAT",
        "desc": "Reversible cotton quilt play mat. Soft padding for tummy time.",
        "tags": ["gear", "play", "quilt"],
        "img": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?w=900&h=900&fit=crop&q=80&sat=-30",
        "alt": "Baby play mat quilt on floor",
    },
    {
        "title": "Stoneware Sippy Cup",
        "type": "Feeding",
        "price": "19.00",
        "sku": "CT-SEED-16-SIPPY",
        "desc": "Weighted stoneware trainer cup with silicone sleeve. Easy-grip shape.",
        "tags": ["feeding", "cup", "mealtime"],
        "img": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=900&h=900&fit=crop&q=80",
        "alt": "Ceramic baby sippy cup",
    },
    {
        "title": "Knit Cable Cardigan",
        "type": "Baby apparel",
        "price": "44.00",
        "sku": "CT-SEED-17-CABLE-CARDIGAN",
        "desc": "Classic cable-knit cardigan with wooden buttons. Cotton-wool blend.",
        "tags": ["apparel", "knit", "layer"],
        "img": "https://images.unsplash.com/photo-1519238263530-99bdd11df2ea?w=900&h=900&fit=crop&q=80",
        "alt": "Knit baby cardigan",
    },
    {
        "title": "Organic Cotton Crib Skirt",
        "type": "Nursery",
        "price": "46.00",
        "sku": "CT-SEED-18-CRIB-SKIRT",
        "desc": "Gathered crib skirt in washed organic cotton. Fits standard crib base.",
        "tags": ["nursery", "bedding", "organic"],
        "img": "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=900&h=900&fit=crop&q=80&sat=-40",
        "alt": "Crib with cotton skirt",
    },
    {
        "title": "Wooden Pull-Along Duck",
        "type": "Toys",
        "price": "27.00",
        "sku": "CT-SEED-19-PULL-DUCK",
        "desc": "Smooth beech pull toy with cotton cord. Painted with non-toxic milk paint.",
        "tags": ["toys", "wood", "pull"],
        "img": "https://images.unsplash.com/photo-1596461404969-9ae70f2167ec?w=900&h=900&fit=crop&q=80&sat=-50",
        "alt": "Wooden pull-along duck toy",
    },
    {
        "title": "Waterproof Picnic Blanket Mini",
        "type": "Gear",
        "price": "38.00",
        "sku": "CT-SEED-20-PICNIC-MINI",
        "desc": "Compact outdoor blanket with waterproof base and cotton top. Folds into pouch.",
        "tags": ["gear", "outdoor", "blanket"],
        "img": "https://images.unsplash.com/photo-1470246973918-29a93221c455?w=900&h=900&fit=crop&q=80",
        "alt": "Picnic blanket for family outings",
    },
    {
        "title": "Cotton Jersey Romper",
        "type": "Baby apparel",
        "price": "31.00",
        "sku": "CT-SEED-21-JERSEY-ROMPER",
        "desc": "Everyday jersey romper with snap crotch and pocket detail.",
        "tags": ["apparel", "romper", "everyday"],
        "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba?w=900&h=900&fit=crop&q=80&sat=-10",
        "alt": "Baby jersey romper",
    },
    {
        "title": "Beeswax Cotton Food Wraps",
        "type": "Feeding",
        "price": "21.00",
        "sku": "CT-SEED-22-BEESWAX",
        "desc": "Set of three reusable beeswax wraps for snacks and leftovers.",
        "tags": ["feeding", "eco", "kitchen"],
        "img": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=900&h=900&fit=crop&q=80",
        "alt": "Beeswax food wraps",
    },
    {
        "title": "Sherpa Lined Baby Mittens",
        "type": "Baby apparel",
        "price": "18.00",
        "sku": "CT-SEED-23-SHERPA-MITTS",
        "desc": "Soft sherpa-lined mittens with stay-on cuffs. For chilly walks.",
        "tags": ["apparel", "winter", "accessories"],
        "img": "https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?w=900&h=900&fit=crop&q=80",
        "alt": "Baby mittens for cold weather",
    },
    {
        "title": "Cotton Canopy Bed Curtain",
        "type": "Nursery",
        "price": "64.00",
        "sku": "CT-SEED-24-CANOPY",
        "desc": "Airy cotton canopy that hangs above crib or toddler bed. Soft drape.",
        "tags": ["nursery", "decor", "canopy"],
        "img": "https://images.unsplash.com/photo-1587654780291-39c9404d746b?w=900&h=900&fit=crop&q=80&sat=-20",
        "alt": "Nursery canopy over crib",
    },
    {
        "title": "Rubberwood Rattle Drum",
        "type": "Toys",
        "price": "23.00",
        "sku": "CT-SEED-25-RATTLE-DRUM",
        "desc": "Gentle wooden rattle drum with soft beads inside. Sensory play.",
        "tags": ["toys", "wood", "sensory"],
        "img": "https://images.unsplash.com/photo-1566454825481-9c31f4b4a5f1?w=900&h=900&fit=crop&q=80&sat=-30",
        "alt": "Wooden baby rattle drum",
    },
    {
        "title": "Organic Cotton Bath Towel Hood",
        "type": "Bath",
        "price": "35.00",
        "sku": "CT-SEED-26-HOOD-TOWEL",
        "desc": "Extra-absorbent hooded towel in organic terry. Generous wrap size.",
        "tags": ["bath", "towel", "organic"],
        "img": "https://images.unsplash.com/photo-1544126592-807ade215a0b?w=900&h=900&fit=crop&q=80&sat=-25",
        "alt": "Hooded baby bath towel",
    },
    {
        "title": "Linen Changing Basket",
        "type": "Nursery",
        "price": "41.00",
        "sku": "CT-SEED-27-CHANGE-BASKET",
        "desc": "Sturdy linen-covered basket for changing essentials. Removable liner.",
        "tags": ["nursery", "storage", "basket"],
        "img": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=900&h=900&fit=crop&q=80&sat=-15",
        "alt": "Linen nursery changing basket",
    },
    {
        "title": "Cotton Stripe Overalls",
        "type": "Bottoms",
        "price": "37.00",
        "sku": "CT-SEED-28-STRIPE-OVERALL",
        "desc": "Classic stripe overalls with adjustable straps and snap legs.",
        "tags": ["apparel", "bottoms", "stripe"],
        "img": "https://images.unsplash.com/photo-1519238263530-99bdd11df2ea?w=900&h=900&fit=crop&q=80&sat=-40",
        "alt": "Baby stripe overalls",
    },
    {
        "title": "Stainless Straw Cup",
        "type": "Feeding",
        "price": "22.00",
        "sku": "CT-SEED-29-STRAW-CUP",
        "desc": "Insulated stainless cup with soft silicone straw and lid.",
        "tags": ["feeding", "cup", "travel"],
        "img": "https://images.unsplash.com/photo-1604881991720-f91add269bed?w=900&h=900&fit=crop&q=80&sat=-20",
        "alt": "Stainless baby straw cup",
    },
    {
        "title": "Waffle Knit Lounge Set",
        "type": "Baby apparel",
        "price": "45.00",
        "sku": "CT-SEED-30-WAFFLE-SET",
        "desc": "Two-piece waffle knit top and pant. Soft stretch for play and naps.",
        "tags": ["apparel", "lounge", "waffle"],
        "img": "https://images.unsplash.com/photo-1522771930-78848d929f64?w=900&h=900&fit=crop&q=80&sat=-35",
        "alt": "Waffle knit baby lounge set",
    },
    {
        "title": "Cedar Keepsake Box",
        "type": "Baby gift",
        "price": "52.00",
        "sku": "CT-SEED-31-KEEPSAKE",
        "desc": "Cedar-lined box for first locks, hospital bands, and tiny shoes.",
        "tags": ["gift", "keepsake", "wood"],
        "img": "https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=900&h=900&fit=crop&q=80",
        "alt": "Wooden baby keepsake box",
    },
    {
        "title": "Cotton Eyelet Bloomers",
        "type": "Bottoms",
        "price": "24.00",
        "sku": "CT-SEED-32-EYELET-BLOOMER",
        "desc": "Sweet eyelet bloomers with soft elastic waist. Pair with any onesie.",
        "tags": ["apparel", "bottoms", "eyelet"],
        "img": "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=900&h=900&fit=crop&q=80&bri=-10",
        "alt": "Cotton eyelet baby bloomers",
    },
    {
        "title": "Wool Dryer Ball Trio",
        "type": "Nursery",
        "price": "17.00",
        "sku": "CT-SEED-33-DRYER-BALLS",
        "desc": "Three pure wool dryer balls. Soften laundry without plastic sheets.",
        "tags": ["nursery", "laundry", "wool"],
        "img": "https://images.unsplash.com/photo-1582735689369-4fe89db7114c?w=900&h=900&fit=crop&q=80",
        "alt": "Wool dryer balls",
    },
    {
        "title": "Linen Weekend Duffel Mini",
        "type": "Bags",
        "price": "68.00",
        "sku": "CT-SEED-34-DUFFEL-MINI",
        "desc": "Small linen duffel for overnight visits. Interior bottle pocket.",
        "tags": ["bags", "travel", "linen"],
        "img": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=900&h=900&fit=crop&q=80",
        "alt": "Small linen weekend duffel",
    },
    {
        "title": "Cotton Pointelle Kimono Top",
        "type": "Baby apparel",
        "price": "28.00",
        "sku": "CT-SEED-35-KIMONO",
        "desc": "Side-tie kimono top in delicate pointelle. Easy changes for newborns.",
        "tags": ["apparel", "newborn", "pointelle"],
        "img": "https://images.unsplash.com/photo-1555252333-9f8e92e65df9?w=900&h=900&fit=crop&q=80&sat=-15",
        "alt": "Pointelle kimono baby top",
    },
    {
        "title": "Silicone Placemat Tray",
        "type": "Feeding",
        "price": "20.00",
        "sku": "CT-SEED-36-PLACEMAT",
        "desc": "One-piece silicone placemat with raised rim. Rolls for travel.",
        "tags": ["feeding", "silicone", "table"],
        "img": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=900&h=900&fit=crop&q=80&sat=-30",
        "alt": "Silicone baby placemat",
    },
    {
        "title": "Rattan Toy Basket",
        "type": "Nursery",
        "price": "49.00",
        "sku": "CT-SEED-37-RATTAN-BASKET",
        "desc": "Open rattan basket for toys and board books. Natural finish.",
        "tags": ["nursery", "storage", "rattan"],
        "img": "https://images.unsplash.com/photo-1595428774223-ef52624120d2?w=900&h=900&fit=crop&q=80",
        "alt": "Rattan nursery toy basket",
    },
    {
        "title": "Cashmere Blend Booties",
        "type": "Baby apparel",
        "price": "33.00",
        "sku": "CT-SEED-38-CASH-BOOTIES",
        "desc": "Ultra-soft cashmere-blend booties with rib cuff. Gift boxed.",
        "tags": ["apparel", "booties", "gift"],
        "img": "https://images.unsplash.com/photo-1485546246426-74dc88dec4d9?w=900&h=900&fit=crop&q=80&sat=-20",
        "alt": "Soft cashmere baby booties",
    },
    {
        "title": "Cotton Seersucker Bubble",
        "type": "Baby apparel",
        "price": "40.00",
        "sku": "CT-SEED-39-SEERSUCKER",
        "desc": "Classic seersucker bubble with snap crotch and back button.",
        "tags": ["apparel", "summer", "seersucker"],
        "img": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?w=900&h=900&fit=crop&q=80&bri=5",
        "alt": "Seersucker baby bubble outfit",
    },
    {
        "title": "Beechwood Push Walker",
        "type": "Toys",
        "price": "79.00",
        "sku": "CT-SEED-40-PUSH-WALKER",
        "desc": "Steady beech push walker with silent wheels. Toddler first steps.",
        "tags": ["toys", "wood", "walker"],
        "img": "https://images.unsplash.com/photo-1566454825481-9c31f4b4a5f1?w=900&h=900&fit=crop&q=80&bri=-5",
        "alt": "Wooden toddler push walker",
    },
    {
        "title": "Organic Cotton Burp Cloth Set",
        "type": "Baby gift",
        "price": "22.00",
        "sku": "CT-SEED-41-BURP-SET",
        "desc": "Set of four absorbent organic burp cloths with colored trim.",
        "tags": ["gift", "burp", "organic"],
        "img": "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=900&h=900&fit=crop&q=80&bri=-5",
        "alt": "Organic cotton burp cloths",
    },
    {
        "title": "Linen Stroller Organizer",
        "type": "Bags",
        "price": "36.00",
        "sku": "CT-SEED-42-STROLLER-ORG",
        "desc": "Clip-on linen organizer with cup pocket and zip pouch.",
        "tags": ["bags", "stroller", "travel"],
        "img": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=900&h=900&fit=crop&q=80&sat=-40",
        "alt": "Linen stroller organizer bag",
    },
    {
        "title": "Cotton Flannel Crib Sheet",
        "type": "Nursery",
        "price": "34.00",
        "sku": "CT-SEED-43-FLANNEL-SHEET",
        "desc": "Brushed flannel crib sheet with deep pocket and strong elastic.",
        "tags": ["nursery", "bedding", "flannel"],
        "img": "https://images.unsplash.com/photo-1587654780291-39c9404d746b?w=900&h=900&fit=crop&q=80&bri=10",
        "alt": "Flannel crib sheet on mattress",
    },
    {
        "title": "Silicone Bath Book Pair",
        "type": "Bath",
        "price": "15.00",
        "sku": "CT-SEED-44-BATH-BOOK",
        "desc": "Two soft silicone bath books that float and squeak gently.",
        "tags": ["bath", "toys", "silicone"],
        "img": "https://images.unsplash.com/photo-1596461404969-9ae70f2167ec?w=900&h=900&fit=crop&q=80&bri=10",
        "alt": "Silicone bath books for babies",
    },
    {
        "title": "Hemp Cotton Tote Diaper Caddy",
        "type": "Bags",
        "price": "47.00",
        "sku": "CT-SEED-45-DIAPER-CADDY",
        "desc": "Open-top diaper caddy with six pockets. Hemp-cotton canvas.",
        "tags": ["bags", "diaper", "caddy"],
        "img": "https://images.unsplash.com/photo-1590874103328-eac38a67478a?w=900&h=900&fit=crop&q=80",
        "alt": "Canvas diaper caddy tote",
    },
    {
        "title": "Merino Sleep Layer Top",
        "type": "Baby apparel",
        "price": "42.00",
        "sku": "CT-SEED-46-MERINO-TOP",
        "desc": "Lightweight merino base layer for cool nights. Flat seams.",
        "tags": ["apparel", "sleep", "merino"],
        "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba?w=900&h=900&fit=crop&q=80&bri=-8",
        "alt": "Merino baby sleep layer",
    },
    {
        "title": "Cotton Rainbow Stack Cups",
        "type": "Toys",
        "price": "25.00",
        "sku": "CT-SEED-47-STACK-CUPS",
        "desc": "Nesting cups in muted rainbow tones. Bath and floor play.",
        "tags": ["toys", "stack", "sensory"],
        "img": "https://images.unsplash.com/photo-1566454825481-9c31f4b4a5f1?w=900&h=900&fit=crop&q=80&sat=20",
        "alt": "Colorful stacking cups toy",
    },
    {
        "title": "Linen Bandana Bib Duo",
        "type": "Baby gift",
        "price": "19.00",
        "sku": "CT-SEED-48-BANDANA-BIB",
        "desc": "Two linen-cotton bandana bibs with snug snaps. Absorbent face.",
        "tags": ["gift", "bib", "linen"],
        "img": "https://images.unsplash.com/photo-1544126592-807ade215a0b?w=900&h=900&fit=crop&q=80&bri=8",
        "alt": "Linen bandana baby bibs",
    },
    {
        "title": "Wool Felt Play Ball Set",
        "type": "Toys",
        "price": "21.00",
        "sku": "CT-SEED-49-FELT-BALLS",
        "desc": "Five soft wool felt balls in nursery neutrals. Quiet indoor play.",
        "tags": ["toys", "felt", "wool"],
        "img": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=900&h=900&fit=crop&q=80",
        "alt": "Wool felt play balls",
    },
    {
        "title": "Organic Cotton Day Quilt",
        "type": "Blankets",
        "price": "76.00",
        "sku": "CT-SEED-50-DAY-QUILT",
        "desc": "Lightweight day quilt with organic batting. Stroller and floor ready.",
        "tags": ["blankets", "quilt", "organic"],
        "img": "https://images.unsplash.com/photo-1555252333-9f8e92e65df9?w=900&h=900&fit=crop&q=80&bri=12",
        "alt": "Organic cotton day quilt",
    },
]

CREATE = """
mutation CreateDemoProduct($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
  productCreate(product: $product, media: $media) {
    product {
      id
      title
      status
      variants(first: 1) { nodes { id } }
    }
    userErrors { field message }
  }
}
"""

UPDATE = """
mutation UpdateVariant($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price sku }
    userErrors { field message }
  }
}
"""

PUBLISH = """
mutation Publish($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    userErrors { field message }
  }
}
"""


def gql(shop: str, ver: str, token: str, query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    req = urllib.request.Request(
        f"https://{shop}/admin/api/{ver}/graphql.json",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc


def create_one(shop: str, ver: str, token: str, item: dict) -> dict:
    tags = [SEED_TAG, *item["tags"]]
    create_res = gql(
        shop,
        ver,
        token,
        CREATE,
        {
            "product": {
                "title": item["title"],
                "descriptionHtml": f"<p>{item['desc']}</p>",
                "vendor": VENDOR,
                "productType": item["type"],
                "status": "ACTIVE",
                "tags": tags,
            },
            "media": [
                {
                    "originalSource": item["img"],
                    "alt": item["alt"],
                    "mediaContentType": "IMAGE",
                }
            ],
        },
    )
    payload = (create_res.get("data") or {}).get("productCreate") or {}
    errors = payload.get("userErrors") or create_res.get("errors") or []
    product = payload.get("product")
    if errors or not product:
        return {"ok": False, "title": item["title"], "errors": errors or create_res}

    product_id = product["id"]
    variant_id = product["variants"]["nodes"][0]["id"]
    update_res = gql(
        shop,
        ver,
        token,
        UPDATE,
        {
            "productId": product_id,
            "variants": [
                {
                    "id": variant_id,
                    "price": item["price"],
                    "inventoryItem": {"sku": item["sku"]},
                }
            ],
        },
    )
    update_errors = (
        ((update_res.get("data") or {}).get("productVariantsBulkUpdate") or {}).get("userErrors")
        or update_res.get("errors")
        or []
    )
    publish_res = gql(
        shop,
        ver,
        token,
        PUBLISH,
        {"id": product_id, "input": [{"publicationId": ONLINE_STORE_PUBLICATION}]},
    )
    publish_errors = (
        ((publish_res.get("data") or {}).get("publishablePublish") or {}).get("userErrors")
        or publish_res.get("errors")
        or []
    )
    return {
        "ok": not update_errors and not publish_errors,
        "id": product_id,
        "title": item["title"],
        "sku": item["sku"],
        "price": item["price"],
        "update_errors": update_errors,
        "publish_errors": publish_errors,
    }


def main() -> int:
    if len(PRODUCTS) != 50:
        print(f"expected 50 products, got {len(PRODUCTS)}", file=sys.stderr)
        return 2
    env = load_shopify_env()
    shop = require_pinned_shop(env)
    token = mint_token(env["SHOPIFY_CLIENT_ID"], env["SHOPIFY_CLIENT_SECRET"], env=env)
    ver = env.get("SHOPIFY_API_VERSION") or "2026-07"
    print(f"seeding {len(PRODUCTS)} products on {shop} ({ver})")
    ok_rows: list[dict] = []
    fail_rows: list[dict] = []
    for index, item in enumerate(PRODUCTS, start=1):
        try:
            result = create_one(shop, ver, token, item)
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "title": item["title"], "errors": [str(exc)]}
        if result.get("ok"):
            ok_rows.append(result)
            print(f"[{index:02d}/50] ok  {result['title']}  {result['sku']}  ${result['price']}")
        else:
            fail_rows.append(result)
            print(f"[{index:02d}/50] FAIL {item['title']}: {result.get('errors') or result}")
        time.sleep(0.35)  # gentle on cost bucket
    print(f"done: {len(ok_rows)} created, {len(fail_rows)} failed")
    out = ROOT / "tools" / "seed_demo_products_result.json"
    out.write_text(json.dumps({"ok": ok_rows, "fail": fail_rows}, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0 if not fail_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())

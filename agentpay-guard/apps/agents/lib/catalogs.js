export const CATALOGS = {
  procurement: {
    purposes: ["buy_office_supplies"],
    vendors: [
      { merchant: "staples.demo", items: ["printer paper", "toner cartridges", "desk organizers"] },
      { merchant: "supplies.vendor.com", items: ["staplers", "notebooks", "whiteboard markers"] },
      { merchant: "paperworld.demo", items: ["A4 paper pallets", "shipping labels"] },
      { merchant: "blocked.vendor.com", items: ["unvetted surplus stock"] }
    ],
    amount_range: [4, 18]
  },
  research: {
    purposes: ["buy_api_credits", "purchase_dataset"],
    vendors: [
      { merchant: "api.vendor.com", items: ["GPT API credits", "embedding API bundle"] },
      { merchant: "data.market.demo", items: ["market research dataset", "sentiment feed"] },
      { merchant: "modelhub.demo", items: ["fine-tune job deposit"] },
      { merchant: "sanctioned-example.test", items: ["restricted data broker API"] },
      {
        merchant: "api.vendor.com",
        items: ["dataset with external wallet settlement"],
        wallet: "0xdead000000000000000000000000000000000000"
      }
    ],
    amount_range: [5, 85]
  },
  travel: {
    purposes: ["book_travel"],
    vendors: [
      { merchant: "hotels.demo", items: ["2-night business hotel", "conference hotel block"] },
      { merchant: "flights.demo", items: ["HK-SG economy", "HK-TYO business class"] },
      { merchant: "rail.demo", items: ["high-speed rail pass"] }
    ],
    amount_range: [12, 120]
  }
};

export function randomId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function pickRandom(list) {
  return list[Math.floor(Math.random() * list.length)];
}

export function randomAmount([min, max]) {
  const value = min + Math.random() * (max - min);
  return value.toFixed(2);
}

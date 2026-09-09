/**
 * Hierarchical National Industrial Classification (NIC-2008) reference data.
 * Used for dynamic 2-digit -> 4-digit -> 5-digit cascading selection in customer intake.
 */

export interface NicItem {
  code: string;
  description: string;
}

export interface NicHierarchy {
  [twoDigitCode: string]: {
    description: string;
    majorType: "Manufacturing" | "Services" | "Trading";
    groups: {
      [fourDigitCode: string]: {
        description: string;
        subClasses: NicItem[];
      };
    };
  };
}

export const NIC_HIERARCHY: NicHierarchy = {
  "01": {
    description: "Crop and animal production, hunting and related service activities",
    majorType: "Manufacturing",
    groups: {
      "0111": {
        description: "Growing of cereals, leguminous crops and oil seeds",
        subClasses: [
          { code: "01111", description: "Growing of wheat" },
          { code: "01112", description: "Growing of rice" },
          { code: "01119", description: "Growing of other cereals and legumes n.e.c." },
        ],
      },
      "0161": {
        description: "Support activities for crop production",
        subClasses: [
          { code: "01611", description: "Preparation of fields and harvesting services" },
          { code: "01619", description: "Other post-harvest crop activities n.e.c." },
        ],
      },
    },
  },
  "10": {
    description: "Manufacture of food products",
    majorType: "Manufacturing",
    groups: {
      "1071": {
        description: "Manufacture of bakery products",
        subClasses: [
          { code: "10711", description: "Manufacture of bread, cakes and fresh pastries" },
          { code: "10712", description: "Manufacture of biscuits, cookies and rusks" },
          { code: "10719", description: "Manufacture of other bakery and snack products n.e.c." },
        ],
      },
      "1079": {
        description: "Manufacture of other food products n.e.c.",
        subClasses: [
          { code: "10791", description: "Manufacture of spices, sauces and condiments" },
          { code: "10792", description: "Manufacture of tea and coffee blending" },
          { code: "10799", description: "Manufacture of packaged ready-to-eat foods" },
        ],
      },
    },
  },
  "13": {
    description: "Manufacture of textiles",
    majorType: "Manufacturing",
    groups: {
      "1311": {
        description: "Preparation and spinning of textile fibres",
        subClasses: [
          { code: "13111", description: "Preparation and spinning of cotton fibre" },
          { code: "13114", description: "Preparation and spinning of synthetic fibre" },
        ],
      },
      "1391": {
        description: "Manufacture of knitted and crocheted fabrics",
        subClasses: [
          { code: "13911", description: "Manufacture of knitted and crocheted fabrics and yarn" },
        ],
      },
    },
  },
  "14": {
    description: "Manufacture of wearing apparel",
    majorType: "Manufacturing",
    groups: {
      "1410": {
        description: "Manufacture of wearing apparel, except fur apparel",
        subClasses: [
          { code: "14101", description: "Manufacture of all types of textile garments and clothing" },
          { code: "14102", description: "Custom tailoring and dressmaking" },
          { code: "14109", description: "Manufacture of other accessories and garments n.e.c." },
        ],
      },
    },
  },
  "25": {
    description: "Manufacture of fabricated metal products",
    majorType: "Manufacturing",
    groups: {
      "2511": {
        description: "Manufacture of structural metal products",
        subClasses: [
          { code: "25111", description: "Manufacture of doors, windows, gates and metal framing" },
          { code: "25119", description: "Manufacture of other metal structures n.e.c." },
        ],
      },
      "2592": {
        description: "Machining, treatment and coating of metals",
        subClasses: [
          { code: "25920", description: "Machining, turning, milling, welding and metal coating" },
        ],
      },
    },
  },
  "45": {
    description: "Wholesale and retail trade and repair of motor vehicles and motorcycles",
    majorType: "Trading",
    groups: {
      "4520": {
        description: "Maintenance and repair of motor vehicles",
        subClasses: [
          { code: "45200", description: "Maintenance, mechanical and electrical repair of automobiles" },
        ],
      },
      "4530": {
        description: "Sale of motor vehicle parts and accessories",
        subClasses: [
          { code: "45300", description: "Wholesale and retail sale of automobile spare parts" },
        ],
      },
    },
  },
  "47": {
    description: "Retail trade, except of motor vehicles and motorcycles",
    majorType: "Trading",
    groups: {
      "4711": {
        description: "Retail sale in non-specialized stores with food, beverages or tobacco",
        subClasses: [
          { code: "47110", description: "Retail sale in grocery stores, department stores and supermarkets" },
        ],
      },
      "4771": {
        description: "Retail sale of clothing, footwear and leather goods in specialized stores",
        subClasses: [
          { code: "47711", description: "Retail sale of readymade garments and clothing accessories" },
        ],
      },
      "4791": {
        description: "Retail sale via mail order houses or via Internet",
        subClasses: [
          { code: "47910", description: "E-commerce and online retail sales of merchandise" },
        ],
      },
    },
  },
  "56": {
    description: "Food and beverage service activities",
    majorType: "Services",
    groups: {
      "5610": {
        description: "Restaurants and mobile food service activities",
        subClasses: [
          { code: "56101", description: "Restaurants and dining without bars" },
          { code: "56102", description: "Cafeterias, fast-food canteens and takeaway services" },
        ],
      },
      "5621": {
        description: "Event catering",
        subClasses: [
          { code: "56210", description: "Event and contract catering services" },
        ],
      },
    },
  },
  "62": {
    description: "Computer programming, consultancy and related activities",
    majorType: "Services",
    groups: {
      "6201": {
        description: "Computer programming activities",
        subClasses: [
          { code: "62011", description: "Writing, modifying, testing and supporting software" },
          { code: "62012", description: "Web design and customized web development" },
          { code: "62013", description: "Mobile application development" },
        ],
      },
      "6202": {
        description: "Computer consultancy and computer facilities management",
        subClasses: [
          { code: "62020", description: "IT infrastructure, systems and cloud consultancy" },
        ],
      },
      "6209": {
        description: "Other information technology and computer service activities",
        subClasses: [
          { code: "62099", description: "Other computer related and IT support services n.e.c." },
        ],
      },
    },
  },
  "69": {
    description: "Legal and accounting activities",
    majorType: "Services",
    groups: {
      "6920": {
        description: "Accounting, bookkeeping and auditing activities; tax consultancy",
        subClasses: [
          { code: "69201", description: "Accounting, auditing and bookkeeping services" },
          { code: "69202", description: "Tax preparation, planning and advisory services" },
        ],
      },
    },
  },
  "70": {
    description: "Activities of head offices; management consultancy activities",
    majorType: "Services",
    groups: {
      "7020": {
        description: "Management consultancy activities",
        subClasses: [
          { code: "70200", description: "Business management, strategy, HR and marketing consulting" },
        ],
      },
    },
  },
  "74": {
    description: "Other professional, scientific and technical activities",
    majorType: "Services",
    groups: {
      "7410": {
        description: "Specialized design activities",
        subClasses: [
          { code: "74101", description: "Interior design and architecture planning" },
          { code: "74102", description: "Graphic, brand and multimedia design" },
        ],
      },
      "7490": {
        description: "Other professional, scientific and technical activities n.e.c.",
        subClasses: [
          { code: "74909", description: "Business brokerage and general commercial consultancy" },
        ],
      },
    },
  },
  "96": {
    description: "Other personal service activities",
    majorType: "Services",
    groups: {
      "9602": {
        description: "Hairdressing and other beauty treatment",
        subClasses: [
          { code: "96020", description: "Salons, beauty parlours and personal grooming services" },
        ],
      },
    },
  },
};

export function getNic2Digits(majorActivity?: string): Array<{ code: string; label: string }> {
  return Object.entries(NIC_HIERARCHY)
    .filter(([_, data]) => !majorActivity || data.majorType.toLowerCase() === majorActivity.toLowerCase() || majorActivity === "Services")
    .map(([code, data]) => ({
      code,
      label: `${code} — ${data.description}`,
    }));
}

export function getNic4Digits(twoDigitCode: string): Array<{ code: string; label: string }> {
  const section = NIC_HIERARCHY[twoDigitCode];
  if (!section) return [];
  return Object.entries(section.groups).map(([code, data]) => ({
    code,
    label: `${code} — ${data.description}`,
  }));
}

export function getNic5Digits(twoDigitCode: string, fourDigitCode: string): Array<{ code: string; label: string }> {
  const section = NIC_HIERARCHY[twoDigitCode];
  if (!section) return [];
  const group = section.groups[fourDigitCode];
  if (!group) return [];
  return group.subClasses.map((item) => ({
    code: item.code,
    label: `${item.code} — ${item.description}`,
  }));
}

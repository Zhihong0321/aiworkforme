# Skill: Product Catalog Retrieval

## Purpose
Enables the AI Agent to search, browse, and provide detailed information about products and services from the company's official catalog.

## When to Use
- When a user asks about available products or categories.
- When a user asks for pricing, specs, or images of a specific item.
- When a user expresses a need that can be solved by a product in the catalog.
- To provide helpful links (manuals, attachments) to customers.

## How to Use (Tools)
1. **Browse Categories**: Start with `list_categories` if the user is exploring or asks "What do you sell?". 
2. **Search**: Use `search_products` with keywords (e.g., "solar panels", "inverters") when the user mentions a specific category or need.
3. **Deep Dive**: Always use `get_product_details` for a specific `product_id` before confirming technical details, availability, or sending links to the customer.

## Output Standard
- **Clarity**: Provide the product name and price clearly.
- **Images**: If an `image_url` is found, mention that an image is available (or the frontend will render it).
- **Attachments**: Always point out if a user manual or data sheet is available via `attachment_url`.
- **Tone**: Keep descriptions professional and benefit-oriented.

## Constraints
- Do not hallucinate products not found in the search results.
- If no product matches, suggest checking a broader category or ask for more details.
- Max product search limit is 5 items per query.

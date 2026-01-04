# Empty State UX Patterns

## Overview

Empty states appear when a list, table, or container has no data. Good empty states guide users toward the next action and prevent confusion.

## Anatomy of a Good Empty State

1. **Icon/Illustration** - Visual indicator that draws attention
2. **Title** - Clear, concise heading
3. **Message** - Helpful explanation
4. **Action** - Button or link to resolve the empty state

## HTML Pattern

```html
<div class="empty-state">
  <div class="empty-state__icon">🍷</div>
  <h3 class="empty-state__title">No wines yet</h3>
  <p class="empty-state__message">Start building your collection by adding your first wine.</p>
  <a href="/wine/add/" class="pure-button button__primary empty-state__action">
    <i class="fa-solid fa-plus"></i> Add Wine
  </a>
</div>
```

## CSS Pattern

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--spacing-xl);
  background: var(--bg-card);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--container-box-shadow);
}

.empty-state__icon {
  font-size: 4rem;
  margin-bottom: var(--spacing-lg);
  opacity: 0.5;
}

.empty-state__title {
  font-size: var(--font-xl);
  color: var(--secondary-dark);
  margin-bottom: var(--spacing-sm);
}

.empty-state__message {
  color: var(--text-color-gray);
  margin-bottom: var(--spacing-lg);
}

.empty-state__action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
}
```

## Widget Empty States

For smaller widgets/cards, use a compact version:

```html
<div class="widget-empty">
  <i class="fa-solid fa-check"></i>
  <span>No alerts</span>
</div>
```

```css
.widget-empty {
  color: var(--text-color-gray);
  text-align: center;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.widget-empty i {
  font-size: var(--font-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-sm);
  opacity: 0.5;
  width: 2.5em;
  height: 2.5em;
  background: var(--bg-secondary);
  border-radius: 50%;
  line-height: 1;
}
```

## Icon Options

### Emojis (Simple, Cross-Platform)
- 🍷 Wine
- 📋 Lists/Reminders
- ✅ Success/Complete
- 💝 Wishlist
- 📦 Storage/Inventory

### FontAwesome Icons
- `fa-solid fa-check` - Success
- `fa-regular fa-heart` - Wishlist
- `fa-regular fa-wine-glass` - Drinks
- `fa-solid fa-wine-bottle` - Wines

## Contextual Messages

| Context | Title | Message |
|---------|-------|---------|
| Wine list | "No wines yet" | "Start building your collection by adding your first wine." |
| Alerts | "All Clear!" | "No wines approaching their drink-by date. Your cellar is in great shape." |
| Reminders | "No Reminders Yet" | "Set up reorder reminders to be notified when your favorite wines run low." |
| Wishlist | "Wishlist is empty" | "Add wines you'd like to try someday." |
| Drink history | "No drinks recorded" | "Record your tastings to track your preferences." |

## Django Template Integration

```django
{% if items %}
  <ul>
    {% for item in items %}
      <li>{{ item.name }}</li>
    {% endfor %}
  </ul>
{% else %}
  <div class="empty-state">
    <div class="empty-state__icon">📋</div>
    <h3 class="empty-state__title">{% translate "No items" %}</h3>
    <p class="empty-state__message">{% translate "Add your first item to get started." %}</p>
    <a href="{% url 'item-add' %}" class="pure-button button__primary empty-state__action">
      <i class="fa-solid fa-plus"></i> {% translate "Add Item" %}
    </a>
  </div>
{% endif %}
```

## Best Practices

1. **Be positive** - "All Clear!" instead of "Nothing here"
2. **Provide context** - Explain why it's empty and what can be done
3. **Include action** - Always provide a next step
4. **Use appropriate icons** - Match the content type
5. **Keep it brief** - Users should understand at a glance
6. **Consider first-time users** - Empty states are often the first thing new users see

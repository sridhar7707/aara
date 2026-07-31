# Motion & Interaction Rules

## Philosophy
Motion in Sentinel exists exclusively to communicate state transitions and preserve user context.

## Allowed Interactions
- Smooth accordion expansion/collapse for evidence packages
- Modal drawer opening and closing
- Subdued state status transitions
- Standard loading indicators for backend data fetching

## Strictly Forbidden
* ❌ Flashing profit/loss alerts or flashing tick animation
* ❌ Pulsing trading indicators or dynamic glowing borders
* ❌ Animated gradients or speculative particle effects
* ❌ Casino-style popups or victory animations on trade approval

## Timing Specifications
- **Standard UI Transitions:** `150ms - 250ms` (`ease-in-out`)
- **Governance & Risk Controls:** `0ms` (Action buttons must be rendered immediately available with zero artificial animation delay).

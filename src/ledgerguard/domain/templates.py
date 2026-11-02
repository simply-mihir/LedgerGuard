"""Business posting template rules and validations for double-entry journals."""

from uuid import UUID

from ledgerguard.domain.models import (
    AccountType,
    JournalPostRequest,
    OperationType,
    PostingSide,
)


class TemplateValidationError(ValueError):
    """Raised when a journal fails business template requirements."""

    pass


def validate_journal_template(
    request: JournalPostRequest,
    account_types: dict[UUID, AccountType],
) -> None:
    """Validate that a journal request satisfies balancing and its business template rules.

    Args:
        request: The journal posting request.
        account_types: Mapping of account_id to AccountType for all accounts referenced.

    Raises:
        TemplateValidationError: If the journal is unbalanced or violates template semantics.
    """
    if len(request.lines) < 2:
        raise TemplateValidationError(
            f"Every committed journal must have at least 2 lines, got {len(request.lines)}."
        )

    debit_total = 0
    credit_total = 0

    for idx, line in enumerate(request.lines):
        if line.account_id not in account_types:
            raise TemplateValidationError(
                f"Line {idx + 1}: Account {line.account_id} not found in account directory/types."
            )
        if line.side == PostingSide.DEBIT:
            debit_total += line.amount.paise
        elif line.side == PostingSide.CREDIT:
            credit_total += line.amount.paise

    if debit_total != credit_total:
        raise TemplateValidationError(
            f"Unbalanced journal: total debits ({debit_total}) != total credits ({credit_total})."
        )

    # Template-specific validation
    op = request.operation_type
    if op == OperationType.FUNDING:
        _validate_two_legged_template(
            request,
            account_types,
            expected_debit_type=AccountType.ASSET,
            expected_credit_type=AccountType.LIABILITY,
            op_name="FUNDING",
        )
    elif op == OperationType.CASH_OUT:
        _validate_two_legged_template(
            request,
            account_types,
            expected_debit_type=AccountType.LIABILITY,
            expected_credit_type=AccountType.ASSET,
            op_name="CASH_OUT",
        )
    elif op == OperationType.LOCAL_TRANSFER:
        _validate_two_legged_template(
            request,
            account_types,
            expected_debit_type=AccountType.LIABILITY,
            expected_credit_type=AccountType.LIABILITY,
            op_name="LOCAL_TRANSFER",
        )
    elif op == OperationType.SOURCE_SETTLE:
        _validate_two_legged_template(
            request,
            account_types,
            expected_debit_type=AccountType.LIABILITY,
            expected_credit_type=AccountType.CONTROL,
            op_name="SOURCE_SETTLE",
        )
    elif op == OperationType.DESTINATION_SETTLE:
        _validate_two_legged_template(
            request,
            account_types,
            expected_debit_type=AccountType.CONTROL,
            expected_credit_type=AccountType.LIABILITY,
            op_name="DESTINATION_SETTLE",
        )
    elif op == OperationType.REVERSAL:
        # Reversal can be between wallets or wallet and control/cash
        pass


def _validate_two_legged_template(
    request: JournalPostRequest,
    account_types: dict[UUID, AccountType],
    expected_debit_type: AccountType,
    expected_credit_type: AccountType,
    op_name: str,
) -> None:
    if len(request.lines) != 2:
        raise TemplateValidationError(
            f"Operation {op_name} requires exactly 2 lines, got {len(request.lines)}."
        )

    line1, line2 = request.lines[0], request.lines[1]
    debit_line = line1 if line1.side == PostingSide.DEBIT else line2
    credit_line = line2 if line1.side == PostingSide.DEBIT else line1

    if debit_line.side != PostingSide.DEBIT or credit_line.side != PostingSide.CREDIT:
        raise TemplateValidationError(
            f"Operation {op_name} must have exactly one DEBIT and one CREDIT."
        )

    debit_acct_type = account_types[debit_line.account_id]
    credit_acct_type = account_types[credit_line.account_id]

    if debit_acct_type != expected_debit_type:
        raise TemplateValidationError(
            f"Operation {op_name} expected DEBIT on {expected_debit_type.value}, got {debit_acct_type.value}."
        )
    if credit_acct_type != expected_credit_type:
        raise TemplateValidationError(
            f"Operation {op_name} expected CREDIT on {expected_credit_type.value}, got {credit_acct_type.value}."
        )
    if debit_line.account_id == credit_line.account_id:
        raise TemplateValidationError(
            f"Operation {op_name} cannot transfer to the same account {debit_line.account_id}."
        )

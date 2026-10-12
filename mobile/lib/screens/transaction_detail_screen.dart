import 'package:flutter/material.dart';

import '../features/rewards/models/reward_transaction.dart';
import '../features/translation/translation_text.dart';

class TransactionDetailScreen extends StatelessWidget {
  final RewardTransaction transaction;

  const TransactionDetailScreen({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    final status = transaction.status == 'SUCCEEDED'
        ? context.tr('Successful')
        : transaction.status == 'FAILED'
            ? context.tr('Failed')
            : context.tr(transaction.status);
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Transaction detail'))),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${transaction.isCredit ? '+' : '-'}₹${transaction.amount}',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  Chip(label: Text(status)),
                  const Divider(height: 28),
                  _row(context.tr('Transaction ID'), transaction.txnId),
                  _row(context.tr('Reward ID'), transaction.rewardId),
                  _row(
                    context.tr('Type'),
                    transaction.isCredit ? context.tr('Reward credit') : context.tr('Reward redemption'),
                  ),
                  _row(context.tr('Date'), transaction.createdAt),
                  if (!transaction.isCredit)
                    _row(context.tr('Payment method'), context.tr('UPI (mock)')),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(context.tr('This record is from the persisted reward ledger. ML price estimates are not payments.'), style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.w600)),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_exception.dart';
import '../../core/idempotency_key_generator.dart';
import '../../features/auth/auth_controller.dart';
import '../../features/ewaste/ewaste_repository.dart';
import '../../features/ewaste/models/submission.dart';
import '../../features/lots/lots_repository.dart';
import '../../features/lots/models/lot.dart';
import '../../features/pricing/widgets/price_trend_card.dart';
import '../../features/translation/translation_text.dart';
import '../../shared/state_views.dart';
import '../../shared/submission_status.dart';

/// The collector's view of one accepted collection's lot: item details,
/// how many recyclers have bid, every bid, and — once the lot is open for
/// bidding — the "Confirm Recycler" action that selects the winner. All
/// data (lot, bids, selection outcome) comes straight from the backend;
/// nothing here is simulated or cached client-side as a source of truth.
class CollectorLotDetailScreen extends StatefulWidget {
  final String lotId;
  const CollectorLotDetailScreen({super.key, required this.lotId});

  @override
  State<CollectorLotDetailScreen> createState() => _CollectorLotDetailScreenState();
}

class _CollectorLotDetailScreenState extends State<CollectorLotDetailScreen> {
  bool _loading = true;
  String? _error;
  Lot? _lot;
  Submission? _item;
  List<Bid> _bids = [];

  String? _selectingBidId;
  String? _actionError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final lot = await context.read<LotsRepository>().getLot(
            accessToken: token,
            lotId: widget.lotId,
          );
      Submission? item;
      if (lot.itemIds.isNotEmpty) {
        item = await context.read<EwasteRepository>().getSubmission(
              lot.itemIds.first,
              token,
            );
      }
      List<Bid> bids = [];
      if (lot.status != 'DRAFT') {
        bids = await context.read<LotsRepository>().listBidsForLot(
              accessToken: token,
              lotId: widget.lotId,
            );
      }
      if (!mounted) return;
      setState(() {
        _lot = lot;
        _item = item;
        _bids = bids;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _selectRecycler(Bid bid) async {
    setState(() {
      _selectingBidId = bid.bidId;
      _actionError = null;
    });
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      await context.read<LotsRepository>().selectRecycler(
            accessToken: token,
            bidId: bid.bidId,
            idempotencyKey: IdempotencyKeyGenerator.generate(),
          );
      await _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _actionError = e.message);
    } finally {
      if (mounted) setState(() => _selectingBidId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Lot Detail'))),
      body: RefreshIndicator(onRefresh: _load, child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading) return const LoadingView();
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          ErrorView(message: _error!, onRetry: _load),
        ],
      );
    }
    final lot = _lot;
    if (lot == null) {
      return ListView(
        children: const [
          SizedBox(height: 80),
          EmptyView(message: 'Lot not found.'),
        ],
      );
    }
    final info = submissionStatusInfo(lot.status, translate: context.tr);
    final acceptedBid = _bids.where((b) => b.status == 'ACCEPTED').isEmpty
        ? null
        : _bids.firstWhere((b) => b.status == 'ACCEPTED');

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${context.tr('Lot')} ${lot.lotId.substring(0, 8)}…',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Chip(
                  label: Text(info.label, style: const TextStyle(color: Colors.white)),
                  backgroundColor: info.color,
                ),
                const Divider(height: 24),
                _row('Material/category', lot.category),
                if (_item?.condition != null) _row('Condition', context.tr(_item!.condition!)),
                if (lot.totalWeightKg != null)
                  _row('Weight', '${lot.totalWeightKg!.toStringAsFixed(2)} kg'),
                if (_item?.priceEstimate != null)
                  _row(
                    'Price estimate',
                    '₹${_item!.priceEstimate!.minPrice.toStringAsFixed(2)} – '
                        '₹${_item!.priceEstimate!.maxPrice.toStringAsFixed(2)} / kg',
                  ),
                if (_item?.homeLat != null && _item?.homeLng != null)
                  _row(
                    'Pickup location',
                    '${_item!.homeLat!.toStringAsFixed(5)}, ${_item!.homeLng!.toStringAsFixed(5)}',
                  ),
                if (_item?.collectionTs != null)
                  _row('Collected at', _item!.collectionTs!.toLocal().toString()),
                if (_item?.photoFileId != null)
                  _row('Photo on file', _item!.photoFileId!),
                if (lot.bidDeadline != null)
                  _row('Bid deadline', lot.bidDeadline!.toLocal().toString()),
              ],
            ),
          ),
        ),
        if (_item?.priceEstimate != null) PriceTrendCard(item: lot.category, wardId: lot.wardId),
        const SizedBox(height: 16),
        _buildBidsSection(acceptedBid),
      ],
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 140,
              child: Text(context.tr(label), style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
            Expanded(child: Text(value)),
          ],
        ),
      );

  Widget _buildBidsSection(Bid? acceptedBid) {
    final lot = _lot!;
    if (lot.status == 'DRAFT') {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(context.tr('This lot has not been listed for bidding yet.')),
        ),
      );
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _bids.isEmpty
                  ? context.tr('No recyclers have bid yet.')
                  : _bids.length == 1
                      ? context.tr('1 recycler has bid')
                      : context.trf('{count} recyclers have bid', {'count': _bids.length}),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (_actionError != null) ...[
              const SizedBox(height: 8),
              Text(context.tr(_actionError!), style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 8),
            for (final bid in _bids) _buildBidRow(bid, acceptedBid),
          ],
        ),
      ),
    );
  }

  Widget _buildBidRow(Bid bid, Bid? acceptedBid) {
    final canSelect = acceptedBid == null && bid.status == 'PLACED';
    final statusLabel = switch (bid.status) {
      'ACCEPTED' => context.tr('Approved / Confirmed'),
      'REJECTED' => context.tr('Rejected / Not Approved'),
      'CANCELLED' => context.tr('Cancelled by recycler'),
      _ => context.tr('Placed'),
    };
    final statusColor = switch (bid.status) {
      'ACCEPTED' => Colors.green,
      'REJECTED' => Colors.red,
      _ => Colors.grey,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(bid.recyclerId, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text('₹${bid.amount}'),
                Text(statusLabel, style: TextStyle(color: statusColor)),
              ],
            ),
          ),
          if (canSelect)
            ElevatedButton(
              key: Key('confirm_recycler_button_${bid.bidId}'),
              onPressed: _selectingBidId == null ? () => _selectRecycler(bid) : null,
              child: _selectingBidId == bid.bidId
                  ? const SizedBox(
                      height: 16,
                      width: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(context.tr('Confirm Recycler')),
            ),
        ],
      ),
    );
  }
}
